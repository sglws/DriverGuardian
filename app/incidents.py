"""
incidents.py
------------
The black box: what happened in the seconds around a dangerous moment.

A session (session.py) is the whole drive at one reading a second, without
pictures. An incident is a short slice of it, kept separately and in more
detail: the camera frames and five readings a second from INCIDENT_PRE_SEC
before the moment to INCIDENT_POST_SEC after it - what an investigator, an
insurer or the driver needs to see what exactly happened.

An incident opens when:
    - the risk turns HIGH (the car starts its pull-over),
    - the ESP32 makes an emergency stop (obstacle or edge),
    - the ESP32 loses the Pi's heartbeat (its own fail-safe pull-over).
Another trigger while one is open joins it and keeps it open a little longer
(never past INCIDENT_MAX_SEC), so one crash is one incident, not five.

Memory: the last ~70 s of frames, already JPEG-encoded at 640 px (~10 MB).
The main loop only hands over a downscaled frame five times a second; the
encoding and every disk write happen on background threads. On disk, one
folder per incident under INCIDENTS_DIR (meta.json, samples.json, frames/),
the oldest removed past INCIDENTS_KEEP.
"""

import io
import json
import os
import queue
import re
import shutil
import threading
import time
import zipfile
from collections import deque

import cv2

from app import config

_ID = re.compile(r"\d{8}-\d{6}(-\d+)?")


class BlackBox:
    def __init__(self, root=None):
        self.root = root or config.INCIDENTS_DIR
        self.enabled = config.INCIDENTS_ENABLED
        self._lock = threading.Lock()
        keep = config.INCIDENT_PRE_SEC + config.INCIDENT_MAX_SEC + 5
        self._frames = deque(maxlen=int(keep * config.INCIDENT_FPS) + 10)    # (t, jpeg bytes)
        self._samples = deque(maxlen=int(keep * 5) + 25)                      # dicts with "t"
        self._raw = queue.Queue(maxsize=4)        # downscaled frames waiting to be encoded
        self._last_frame = -1e9
        self._open = None                         # the incident being recorded
        self._prev = {}
        self._manual = None                       # a reason, when the dashboard asked to save now
        self._last_kind = {}                      # trigger kind -> when it last started an incident
        self._list_cache = None
        self._latest = None                       # newest saved incident id (the dashboard's badge)
        self.active = False                       # switched on/off from the dashboard; remembered in settings.json
        if self.enabled:
            os.makedirs(self.root, exist_ok=True)
            self._latest = max(self._ids(), default=None)
            self.active = self._read_settings().get("active", True)
            threading.Thread(target=self._encoder, daemon=True, name="blackbox-jpeg").start()

    # ------------------------------------------------------------ main loop (fast)

    def add_frame(self, frame, now: float):
        """Called every frame; keeps INCIDENT_FPS of them. Never blocks."""
        if not self.active or now - self._last_frame < 1.0 / config.INCIDENT_FPS:
            return
        self._last_frame = now
        h, w = frame.shape[:2]
        if w > config.INCIDENT_WIDTH:
            frame = cv2.resize(frame, (config.INCIDENT_WIDTH, round(h * config.INCIDENT_WIDTH / w)),
                               interpolation=cv2.INTER_AREA)
        else:
            frame = frame.copy()        # the main loop keeps drawing on its own array
        try:
            self._raw.put_nowait((now, frame))
        except queue.Full:
            pass                        # a slow moment: one missing frame beats a stalled loop

    def update(self, state: dict, sample: dict, now: float, session_id=None, session_label=""):
        """Called with every dashboard state (session.py). Returns the titles
        of triggers that opened or joined an incident, for the event log."""
        if not self.active:
            return []
        with self._lock:
            self._samples.append(sample)
            fired = self._triggers(state)
            if fired and self._open is None:
                # a flickering sensor (an obstacle at ~10 cm) must not fill the list with copies
                # and push real incidents out: a kind that just started one waits its cooldown
                fired = [f for f in fired if f[1] == "manual"
                         or now - self._last_kind.get(f[1], -1e9) >= config.INCIDENT_COOLDOWN_SEC]
            if fired and self._open is not None:
                # the same trigger again (a flickering sensor): counted once, and it doesn't keep
                # the incident open; a different trigger joins it and extends it
                have = {t["kind"]: t for t in self._open["triggers"]}
                for title, kind in fired:
                    if kind in have:
                        have[kind]["repeats"] = have[kind].get("repeats", 0) + 1
                fired = [f for f in fired if f[1] not in have]
            if fired:
                if self._open is None:
                    wall = time.time()
                    self._open = {"id": self._new_id(wall), "t0": now, "ts0": wall,
                                  "end": now + config.INCIDENT_POST_SEC, "triggers": [],
                                  "session_id": session_id, "session_label": session_label,
                                  "at_trigger": _situation(state)}
                else:
                    self._open["end"] = min(self._open["t0"] + config.INCIDENT_MAX_SEC,
                                            now + config.INCIDENT_POST_SEC)
                for title, kind in fired:
                    self._last_kind[kind] = now
                    self._open["triggers"].append({"offset_s": round(now - self._open["t0"], 2),
                                                   "kind": kind, "title": title})
            if self._open is not None and now >= self._open["end"]:
                self._finish()
            return [t for t, _ in fired]

    def status(self):
        with self._lock:
            return {"active": self.active, "recording": self._open is not None,
                    "id": self._open["id"] if self._open else None, "latest": self._latest}

    def set_active(self, on: bool):
        """Switch the black box on or off. Off: an incident being recorded is
        saved with what there is, and the frames in memory are dropped - the
        camera is no longer kept at all."""
        if not self.enabled:
            return
        on = bool(on)
        with self._lock:
            if on == self.active:
                return
            self.active = on
            if not on:
                if self._open is not None:
                    self._finish()
                self._frames.clear()
                self._samples.clear()
                self._prev = {}           # back on: the current state is not a new trigger
        try:
            _dump(os.path.join(self.root, "settings.json"), {"active": on})
        except OSError as e:
            print(f"[incident] could not remember the setting: {e}")
        print(f"[incident] black box {'on' if on else 'off'}")

    def _read_settings(self):
        try:
            with open(os.path.join(self.root, "settings.json")) as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_now(self, reason="Saved from the dashboard"):
        """A manual incident: the last INCIDENT_PRE_SEC plus what follows."""
        with self._lock:
            self._manual = reason

    def close(self):
        """App stopping: write an open incident with what there is."""
        with self._lock:
            th = self._finish() if self._open is not None else None
        if th:
            th.join(timeout=10)          # outside the lock: the writer takes it when done

    # ------------------------------------------------------------ triggers

    def _triggers(self, s):
        out = []
        risk = s.get("risk")
        active = not s.get("calibrating") and not s.get("paused") and s.get("case") != "TEST"
        if self._edge("high", active and risk == "HIGH"):
            out.append((f"High risk: {_case_name(s.get('case'))} - the car pulls over", "high_risk"))
        v = (s.get("links") or {}).get("vehicle") or {}
        estop = v.get("estop")
        if self._edge("estop", bool(estop)):
            out.append(("Emergency stop: obstacle within 10 cm" if estop == "obstacle"
                        else "Emergency stop: edge of the surface", "emergency_stop"))
        if self._edge("link", bool(v.get("link_failed"))):
            out.append(("ESP32 lost the Pi's heartbeat - fail-safe pull-over", "link_lost"))
        if self._manual:
            out.append((self._manual, "manual"))
            self._manual = None
        return out

    def _edge(self, key, on):
        """True when `on` just became true (never on the first observation)."""
        was = self._prev.get(key)
        self._prev[key] = on
        return bool(on and was is False)

    def _new_id(self, wall):
        base = time.strftime("%Y%m%d-%H%M%S", time.localtime(wall))
        i, cand = 1, base
        while os.path.exists(os.path.join(self.root, cand)):
            i += 1
            cand = f"{base}-{i}"
        return cand

    def _finish(self):
        """Close the open incident (lock held) and write it on a thread."""
        inc, self._open = self._open, None
        t_from, t_to = inc["t0"] - config.INCIDENT_PRE_SEC, inc["end"]
        frames = [(t, j) for t, j in self._frames if t_from <= t <= t_to]
        samples = [dict(s) for s in self._samples if t_from <= s["t"] <= t_to]
        th = threading.Thread(target=self._write, args=(inc, frames, samples), daemon=True, name="blackbox-write")
        th.start()
        return th

    # ------------------------------------------------------------ background

    def _encoder(self):
        q = [cv2.IMWRITE_JPEG_QUALITY, config.INCIDENT_JPEG_QUALITY]
        while True:
            t, frame = self._raw.get()
            ok, buf = cv2.imencode(".jpg", frame, q)
            if ok:
                with self._lock:
                    self._frames.append((t, buf.tobytes()))

    def _write(self, inc, frames, samples):
        d = os.path.join(self.root, inc["id"])
        try:
            os.makedirs(os.path.join(d, "frames"))
            t0, ts0 = inc["t0"], inc["ts0"]
            for i, (_, jpg) in enumerate(frames):
                with open(os.path.join(d, "frames", f"{i:05d}.jpg"), "wb") as f:
                    f.write(jpg)
            for s in samples:
                s["offset_s"] = round(s.pop("t") - t0, 2)
            meta = {
                "id": inc["id"], "ts": ts0, "session_id": inc["session_id"], "session_label": inc["session_label"],
                "triggers": inc["triggers"], "at_trigger": inc["at_trigger"],
                "pre_s": config.INCIDENT_PRE_SEC, "duration_s": round(inc["end"] - t0 + config.INCIDENT_PRE_SEC, 1),
                "frames": [round(t - t0, 2) for t, _ in frames],
            }
            _dump(os.path.join(d, "samples.json"), samples)
            _dump(os.path.join(d, "meta.json"), meta)        # written last: its presence means "complete"
            with self._lock:
                self._latest = inc["id"]
            print(f"[incident] saved {inc['id']}: {', '.join(t['title'] for t in inc['triggers'])} "
                  f"({len(frames)} frames)")
        except OSError as e:
            print(f"[incident] could not save {inc['id']}: {e}")
        self._prune()

    def _prune(self):
        with self._lock:
            self._list_cache = None
        ids = sorted(self._ids())
        for old in ids[:-config.INCIDENTS_KEEP] if len(ids) > config.INCIDENTS_KEEP else []:
            shutil.rmtree(os.path.join(self.root, old), ignore_errors=True)

    # ------------------------------------------------------------ reading (web_view)

    def _ids(self):
        try:
            return [n for n in os.listdir(self.root)
                    if _ID.fullmatch(n) and os.path.exists(os.path.join(self.root, n, "meta.json"))]
        except OSError:
            return []

    def list(self):
        with self._lock:
            if self._list_cache is not None:
                return self._list_cache
        out = []
        for i in sorted(self._ids(), reverse=True):
            m = self._meta(i)
            if m:
                out.append({k: m[k] for k in ("id", "ts", "session_id", "session_label", "triggers", "at_trigger", "duration_s")}
                           | {"frame_count": len(m.get("frames") or [])})
        with self._lock:
            self._list_cache = out
        return out

    def get(self, iid):
        m = self._meta(iid)
        if m is None:
            return None
        try:
            with open(os.path.join(self.root, iid, "samples.json")) as f:
                m["samples"] = json.load(f)
        except (OSError, ValueError):
            m["samples"] = []
        return m

    def frame(self, iid, n):
        if not _ID.fullmatch(iid or ""):
            return None
        try:
            with open(os.path.join(self.root, iid, "frames", f"{int(n):05d}.jpg"), "rb") as f:
                return f.read()
        except (OSError, ValueError):
            return None

    def zip(self, iid):
        """The whole incident as one download: frames, readings as CSV, a summary."""
        m = self.get(iid)
        if m is None:
            return None
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("summary.txt", _summary_text(m))
            z.writestr("meta.json", json.dumps({k: v for k, v in m.items() if k != "samples"}, indent=1))
            z.writestr("readings.csv", _csv(m["samples"]))
            for i, off in enumerate(m.get("frames") or []):
                jpg = self.frame(iid, i)
                if jpg:
                    z.writestr(f"frames/{i:05d}_{off:+08.2f}s.jpg", jpg, zipfile.ZIP_STORED)
        return buf.getvalue()

    def delete(self, iid):
        if not _ID.fullmatch(iid or ""):
            return False
        shutil.rmtree(os.path.join(self.root, iid), ignore_errors=True)
        latest = max(self._ids(), default=None)
        with self._lock:
            self._list_cache, self._latest = None, latest
        return True

    def _meta(self, iid):
        if not _ID.fullmatch(iid or ""):
            return None
        try:
            with open(os.path.join(self.root, iid, "meta.json")) as f:
                return json.load(f)
        except (OSError, ValueError):
            return None


# ---------------------------------------------------------------- helpers

_CASES = {"SLEEP": "driver asleep", "YAWN": "yawning", "PHONE": "phone use", "SEATBELT": "seatbelt off",
          "ALCOHOL": "alcohol detected", "ABSENT": "driver absent", "BLOCKED": "camera blocked"}


def _case_name(case):
    return _CASES.get(str(case or "").upper(), str(case or "unknown").lower().replace("_", " "))


def _situation(s):
    """The facts at the moment of the trigger, readable without the charts."""
    eyes, objects, head = s.get("eyes") or {}, s.get("objects") or {}, s.get("head") or {}
    v = (s.get("links") or {}).get("vehicle") or {}
    return {
        "risk": s.get("risk"), "case": s.get("case"), "message": (s.get("messages") or [""])[0],
        "driver": s.get("presence"), "face_found": s.get("face_found"),
        "eyes_closed": eyes.get("closed"), "eyes_closed_s": eyes.get("closed_sec"),
        "yawning": (s.get("mouth") or {}).get("yawning"), "looking": head.get("yaw_label"),
        "phone": objects.get("phone"), "eating_drinking": objects.get("consumption"),
        "smoking": objects.get("cigarette"), "seatbelt": objects.get("seatbelt"),
        "alcohol_rel": (s.get("cabin") or {}).get("mq3_rel"),
        "left_pwm": v.get("left_pwm"), "right_pwm": v.get("right_pwm"), "base_pwm": v.get("base_pwm"),
        "front_cm": v.get("front_cm"), "rear_cm": v.get("rear_cm"), "estop": v.get("estop"),
        "link_failed": v.get("link_failed"),
    }


def _dump(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, separators=(",", ":"))
    os.replace(tmp, path)


def _csv(samples):
    import csv
    if not samples:
        return ""
    keys = ["offset_s", "time"] + [k for k in samples[0] if k not in ("offset_s", "ts")]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for s in samples:
        w.writerow({**s, "time": time.strftime("%H:%M:%S", time.localtime(s["ts"])) + f".{int(s['ts'] % 1 * 10)}"})
    return buf.getvalue()


def _summary_text(m):
    a = m.get("at_trigger") or {}
    yes = lambda b: "yes" if b else "no"
    lines = [
        "DriverGuardian incident report",
        "==============================",
        f"Incident:   {m['id']}",
        f"Time:       {time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(m['ts']))}",
        f"Session:    {m.get('session_label') or '-'} (id {m.get('session_id')})",
        f"Recording:  {m['pre_s']:.0f} s before to {m['duration_s'] - m['pre_s']:.0f} s after the first trigger",
        "",
        "What happened (seconds after the first trigger):",
        *[f"  +{t['offset_s']:5.1f} s  {t['title']}" + (f" (and {t['repeats']} more times)" if t.get("repeats") else "")
          for t in m.get("triggers") or []],
        "",
        "At the moment of the first trigger:",
        f"  Risk:            {a.get('risk')} ({_case_name(a.get('case'))})",
        f"  Driver:          {a.get('driver') or '-'}, face {'tracked' if a.get('face_found') else 'not seen'}",
        f"  Eyes closed:     {yes(a.get('eyes_closed'))}" + (f" for {a['eyes_closed_s']:.1f} s" if a.get("eyes_closed_s") else ""),
        f"  Phone in hand:   {yes(a.get('phone'))}",
        f"  Seatbelt:        {a.get('seatbelt') or '-'}",
        f"  Motors (PWM):    left {a.get('left_pwm', '-')}, right {a.get('right_pwm', '-')} (base {a.get('base_pwm', '-')})",
        f"  Front distance:  {a['front_cm']} cm" if a.get("front_cm") is not None else "  Front distance:  clear",
        f"  Emergency stop:  {a.get('estop') or 'no'}",
        "",
        "Files: frames/ holds the camera images (name = seconds from the trigger),",
        "readings.csv the measurements five times a second.",
    ]
    return "\n".join(lines) + "\n"

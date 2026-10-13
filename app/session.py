"""
session.py
----------
One monitoring session at a time: turns the main loop's state updates into
an event log, statistics and a timeline - kept live in memory for the
dashboard and saved to the history database (storage.py) as it happens.

Works whether or not anyone has the dashboard open. The main loop calls
update() a few times a second (wants_update()); everything here is fast and
never waits on the database.
"""

import threading
import time
from collections import deque

from app import config
from app.storage import FLAG_BITS

RISK_ORDER = ["WAITING", "SAFE", "LOW", "MEDIUM", "HIGH"]
_RISK_LEVEL = {"HIGH": "critical", "MEDIUM": "serious", "LOW": "warning", "SAFE": "good"}
PERCLOS_WINDOW_SEC = 60.0      # PERCLOS: share of the last minute with the eyes closed
MAX_EPISODES = 1000


class SessionRecorder:
    def __init__(self, store=None):
        self.store = store
        self._lock = threading.Lock()
        self.session_id = None
        self.label = ""
        self._last_update = None
        self._reset()

    # ------------------------------------------------------------ lifecycle

    def _reset(self):
        self.started_mono = time.monotonic()
        self.started_ts = time.time()
        self._state, self._state_at = {}, 0.0
        self._history = deque(maxlen=int(config.WEB_HISTORY_SEC / config.WEB_HISTORY_INTERVAL_SEC))
        self._events = deque(maxlen=500)
        self._event_id = getattr(self, "_event_id", 0)   # ids stay unique across sessions (live log)
        self._last_sample = self._last_saved_sample = self._last_summary = 0.0
        self._time_in = {r: 0.0 for r in RISK_ORDER}
        self._alerts = {}
        self._prev = {}
        self._pending_risk = None
        self._logged_risk = None
        self._last_update = None
        self._perf = {"fps_sum": 0.0, "fps_n": 0, "gap_max_ms": None, "updates": 0}
        self._baseline = None
        self._tests = []
        self._closed = deque()          # (t, eyes closed) for PERCLOS
        self._episodes = []             # finished alert episodes (see _episode_*)
        self._episode = None
        self._last_voice = None         # wall time of the last spoken alert

    def start(self, label: str = ""):
        with self._lock:
            self._reset()
            self.label = label or time.strftime("Session %d %b %H:%M")
            self.session_id = self.store.new_session(self.label) if self.store else None
            self._append_event("system", "info", "Session started", self.label)

    def end(self, reason: str = "stopped"):
        with self._lock:
            if self.session_id is None:
                return
            self._episode_close(time.time(), still_open=True)
            self._append_event("system", "info", "Session ended", reason)
            if self.store:
                self.store.update_session(self.session_id, summary=self._summary(), ended_ts=time.time())
            self.session_id = None

    def set_label(self, label: str):
        label = label.strip()[:120]
        if not label:
            return
        with self._lock:
            self.label = label
            if self.store and self.session_id is not None:
                self.store.update_session(self.session_id, label=label)

    # ------------------------------------------------------------ main loop

    def wants_update(self, now: float) -> bool:
        return self._last_update is None or now - self._last_update >= config.WEB_STATUS_INTERVAL_SEC

    def update(self, state: dict, now: float):
        with self._lock:
            if self._last_update is not None and self._prev.get("risk") in self._time_in:
                self._time_in[self._prev["risk"]] += now - self._last_update
            self._last_update = now
            self._detect_events(state, now)
            self._track_perf(state)
            state["perclos"] = self._perclos(state, now)
            state["session"] = {
                "id": self.session_id, "label": self.label,
                "started_ts": self.started_ts, "uptime_s": now - self.started_mono,
                "time_in": dict(self._time_in), "alerts": dict(self._alerts),
                "recording": self.session_id is not None,
            }
            self._state, self._state_at = state, now

            if now - self._last_sample >= config.WEB_HISTORY_INTERVAL_SEC:
                self._last_sample = now
                sample = self._sample(state, now)
                self._history.append(sample)
                if self.store and self.session_id is not None and now - self._last_saved_sample >= 1.0:
                    self._last_saved_sample = now
                    self.store.add_sample(self.session_id, sample)
            if self.store and self.session_id is not None and now - self._last_summary >= 30.0:
                self._last_summary = now              # keeps an interrupted session's stats current
                self.store.update_session(self.session_id, summary=self._summary())

    def log(self, kind: str, level: str, title: str, detail: str = ""):
        """Add an event (kind: risk / voice / detect / system / marker / test)."""
        with self._lock:
            self._append_event(kind, level, title, detail)

    def add_test(self, result: dict):
        """A finished dashboard test (app/testing.py) - kept in the summary."""
        with self._lock:
            self._tests.append(result)
            if self.store and self.session_id is not None:
                self.store.update_session(self.session_id, summary=self._summary())

    def mark(self, text: str):
        self.log("marker", "info", (text or "Marker").strip()[:120], "")

    # ------------------------------------------------------------ dashboard reads

    def live_summary(self):
        """The running session's summary as of now (the database copy is
        only refreshed every 30 s)."""
        with self._lock:
            return self._summary()

    def snapshot(self):
        with self._lock:
            return dict(self._state), self._state_at

    def history_since(self, t: float):
        with self._lock:
            return [s for s in self._history if s["t"] > t]

    def events_since(self, event_id: int):
        with self._lock:
            return [e for e in self._events if e["id"] > event_id]

    # ------------------------------------------------------------ internals

    def _perclos(self, s, now):
        """Share of the last minute the eyes were closed (only while a face
        is tracked and monitoring runs). None until 20 s of data exist."""
        eyes = s.get("eyes")
        if eyes and s.get("face_found") and not s.get("calibrating"):
            self._closed.append((now, bool(eyes.get("closed"))))
        while self._closed and now - self._closed[0][0] > PERCLOS_WINDOW_SEC:
            self._closed.popleft()
        if len(self._closed) < 2 or self._closed[-1][0] - self._closed[0][0] < 20.0:
            return None
        return round(sum(c for _, c in self._closed) / len(self._closed), 3)

    @staticmethod
    def _flags(s):
        eyes, mouth, head = s.get("eyes") or {}, s.get("mouth") or {}, s.get("head") or {}
        objects, face = s.get("objects") or {}, s.get("face_found")
        on = {
            "eyes_closed": face and eyes.get("closed"),
            "yawning": face and mouth.get("yawning"),
            "looking_away": face and (head.get("turn_sec") or 0) > 0,
            "head_lean": face and (head.get("lean_sec") or 0) > 0,
            "phone": objects.get("phone"),
            "eating_drinking": objects.get("consumption"),
            "smoking": objects.get("cigarette"),
            "seatbelt_off": objects.get("seatbelt") == "OFF",
            "driver_absent": s.get("presence") == "DRIVER_ABSENT",
            "camera_blocked": s.get("presence") == "CAMERA_BLOCKED",
        }
        return sum(bit for k, bit in FLAG_BITS.items() if on[k])

    @staticmethod
    def _cabin(state):
        """Cabin air sensors (Arduino Uno): raw values, and relative to clean air once warm."""
        c = state.get("cabin") or {}
        return {"mq3": c.get("mq3"), "mq2": c.get("mq2"), "mq3_rel": c.get("mq3_rel"), "mq2_rel": c.get("mq2_rel")}

    @classmethod
    def _sample(cls, state, now):
        eyes, mouth, head = state.get("eyes") or {}, state.get("mouth") or {}, state.get("head") or {}
        counters = {"blinks": eyes.get("blinks_total"), "yawns": mouth.get("yawns_total")}
        if not state.get("face_found"):
            # no face: the app's placeholder EAR/MAR/pose aren't measurements -
            # leave a gap in the charts instead
            eyes, mouth, head = {"ear_thr": eyes.get("ear_thr")}, {"mar_thr": mouth.get("mar_thr")}, {}
        return {
            "t": round(now, 3), "ts": time.time(),
            "risk": state.get("risk"), "case": state.get("case"),
            "ear": eyes.get("ear"), "ear_thr": eyes.get("ear_thr"),
            "mar": mouth.get("mar"), "mar_thr": mouth.get("mar_thr"),
            "pitch": head.get("pitch"), "yaw": head.get("yaw"),
            "fps": (state.get("perf") or {}).get("fps"),
            "flags": None if state.get("calibrating") else cls._flags(state),
            **cls._cabin(state),
            "perclos": state.get("perclos"),
            **counters,
        }

    def _track_perf(self, s):
        perf = s.get("perf") or {}
        if perf.get("fps"):
            self._perf["fps_sum"] += perf["fps"]
            self._perf["fps_n"] += 1
        if perf.get("gap_session_ms") is not None:
            self._perf["gap_max_ms"] = perf["gap_session_ms"]
        if perf.get("updates_total") is not None:
            self._perf["updates"] = perf["updates_total"]
        if s.get("baseline"):
            self._baseline = s["baseline"]
        self._requirements = s.get("requirements")

    def _summary(self):
        p = self._perf
        return {
            "time_in": dict(self._time_in), "alerts": dict(self._alerts),
            "duration_s": time.monotonic() - self.started_mono,
            "avg_fps": round(p["fps_sum"] / p["fps_n"], 1) if p["fps_n"] else None,
            "gap_max_ms": p["gap_max_ms"],
            # classifications per second of actual monitoring (calibration,
            # waiting and pauses excluded) - the update-rate requirement
            "avg_rate_hz": round(p["updates"] / monitored, 1) if (monitored := sum(
                v for k, v in self._time_in.items() if k != "WAITING")) > 1 else None,
            "requirements": getattr(self, "_requirements", None),
            "baseline": self._baseline,
            "markers": sum(1 for e in self._events if e["kind"] == "marker"),
            "tests": list(self._tests),
            # every alert: when it was spoken and when the driver corrected it
            "episodes": self._episodes + ([self._episode_view(time.time())] if self._episode else []),
        }

    # ------------------------------------------------------------ alert episodes
    # An episode is one stretch of LOW/MEDIUM/HIGH risk for one reason (case).
    # voice_s: alert start -> spoken alert; fix_s: spoken alert -> risk back
    # down (the driver corrected it). Times from the risk change's real start.

    def _episode_view(self, end_ts, still_open=True):
        e = self._episode
        return {"case": e["case"], "peak": e["peak"], "start": round(e["start"], 2),
                "dur": round(end_ts - e["start"], 2),
                "voice_s": None if e["voice"] is None else round(max(0.0, e["voice"] - e["start"]), 2),
                "fix_s": None if (e["voice"] is None or still_open) else round(end_ts - e["voice"], 2),
                "open": still_open}

    def _episode_close(self, end_ts, still_open=False):
        if self._episode is None:
            return
        if len(self._episodes) < MAX_EPISODES:
            self._episodes.append(self._episode_view(end_ts, still_open))
        self._episode = None

    def _episode_change(self, risk, case, start_ts):
        rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        active = risk in rank and case not in ("NONE", None)
        e = self._episode
        if e and active and case == e["case"]:
            if rank[risk] > rank[e["peak"]]:
                e["peak"] = risk               # same problem, escalated
            return
        self._episode_close(start_ts)
        if active:
            # a critical alert speaks at once - before the 0.5 s debounce opens the episode
            # (the risk change is stamped at the recorder's next update, up to ~0.2 s late)
            voice = self._last_voice if self._last_voice is not None and self._last_voice >= start_ts - 0.3 else None
            self._episode = {"case": case, "peak": risk, "start": start_ts, "voice": voice}

    def _append_event(self, kind, level, title, detail="", ts=None):
        self._event_id += 1
        e = {"id": self._event_id, "ts": ts or time.time(), "kind": kind,
             "level": level, "title": title, "detail": detail}
        self._events.append(e)
        if self.store and self.session_id is not None:
            self.store.add_event(self.session_id, e)

    def _changed(self, key, value):
        """(changed, old) - never 'changed' on the first observation."""
        missing = key not in self._prev
        old = self._prev.get(key)
        self._prev[key] = value
        return (not missing and old != value), old

    def _detect_events(self, s, now):
        risk, case = s.get("risk"), s.get("case")
        self._prev["risk"] = risk

        # A risk change is logged once it has held for 0.5 s, so a one-frame
        # flicker doesn't flood the log; stamped with when the change began.
        if self._pending_risk is None or self._pending_risk[:2] != (risk, case):
            self._pending_risk = (risk, case, now, time.time())
        elif (now - self._pending_risk[2] >= 0.5 and self._logged_risk != (risk, case)
              and not s.get("calibrating") and case not in ("PAUSED", "TEST")):
            self._logged_risk = (risk, case)
            if risk == "WAITING":
                title = "Waiting for seatbelt" if case == "PRE_DRIVE" else "Waiting"
            else:
                title = f"{risk.title()} risk"
                if case not in ("NONE", None):
                    title += ": " + case.replace("_", " ").lower()
            self._append_event("risk", _RISK_LEVEL.get(risk, "info"), title,
                               " / ".join((s.get("messages") or [])[:2]), ts=self._pending_risk[3])
            self._episode_change(risk, case, self._pending_risk[3])
            if risk in ("LOW", "MEDIUM", "HIGH") and case not in ("NONE", None):
                self._alerts[case] = self._alerts.get(case, 0) + 1

        if self._episode and (risk == "WAITING" or s.get("calibrating")):
            self._episode_close(time.time(), still_open=False)   # paused, test, recalibration

        changed, _ = self._changed("paused", bool(s.get("paused")))
        if changed:
            self._append_event("system", "info", "Monitoring paused" if s.get("paused") else "Monitoring resumed")

        links = s.get("links") or {}
        changed, _ = self._changed("voice_seq", links.get("voice_seq"))
        if changed and links.get("voice_last_age") is not None:
            self._last_voice = time.time() - links["voice_last_age"]
            if self._episode and self._episode["voice"] is None:
                self._episode["voice"] = self._last_voice
        if changed and links.get("voice_last"):
            self._append_event("voice", "info", "Spoken alert", f"“{links['voice_last']}”")
        changed, _ = self._changed("muted", bool(links.get("muted")))
        if changed:
            self._append_event("system", "info", "Voice muted" if links.get("muted") else "Voice unmuted")
        cabin = s.get("cabin") or {}
        changed, _ = self._changed("cabin_ref", bool(cabin.get("baseline")))
        if changed and cabin.get("baseline"):
            self._append_event("system", "good", "Air sensors ready",
                               f"warmed up; clean-air reference MQ-3 {cabin['baseline']['mq3']:.0f}, MQ-2 {cabin['baseline']['mq2']:.0f}")
        for key, label in (("esp32", "ESP32 link"), ("yolo", "Object detection"), ("uno", "Cabin sensors (Arduino)")):
            changed, old = self._changed(key, links.get(key))
            if changed:
                ok = links.get(key) in ("connected", "running")
                self._append_event("system", "good" if ok else "warning",
                                   f"{label} {links.get(key)}", f"was {old}")

        vehicle = links.get("vehicle") or {}
        changed, _ = self._changed("estop", vehicle.get("estop"))
        if changed and vehicle.get("estop"):
            self._append_event("detect", "critical", f"Vehicle emergency stop: {vehicle['estop']}",
                               "ultrasonic: obstacle within 10 cm" if vehicle["estop"] == "obstacle"
                               else "IR sensor: edge of the surface")

        changed, _ = self._changed("calibrating", bool(s.get("calibrating")))
        if changed:
            if s.get("calibrating"):
                self._append_event("system", "info", "Calibration started",
                                   "look straight at the camera, eyes open, mouth closed")
            else:
                b = s.get("baseline") or {}
                self._append_event("system", "good", "Calibration complete",
                                   f"EAR {b.get('ear', 0):.3f}, MAR {b.get('mar', 0):.3f}")

        seatbelt = (s.get("objects") or {}).get("seatbelt")
        changed, _ = self._changed("seatbelt", seatbelt)
        if changed and seatbelt in ("ON", "OFF"):
            self._append_event("detect", "good" if seatbelt == "ON" else "warning", f"Seatbelt {seatbelt.lower()}")
        presence = s.get("presence")
        changed, _ = self._changed("presence", presence)
        if changed and presence:
            self._append_event("detect", "good" if presence == "DRIVER_PRESENT" else "critical",
                               presence.replace("_", " ").capitalize())
        throttled = (s.get("system") or {}).get("throttled") or []
        changed, _ = self._changed("throttled", bool(throttled))
        if changed and throttled:
            self._append_event("system", "critical", "CPU throttling", ", ".join(throttled))

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

RISK_ORDER = ["WAITING", "SAFE", "LOW", "MEDIUM", "HIGH"]
_RISK_LEVEL = {"HIGH": "critical", "MEDIUM": "serious", "LOW": "warning", "SAFE": "good"}


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
        """Add an event (kind: risk / voice / detect / system / marker)."""
        with self._lock:
            self._append_event(kind, level, title, detail)

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

    @staticmethod
    def _sample(state, now):
        eyes, mouth, head = state.get("eyes") or {}, state.get("mouth") or {}, state.get("head") or {}
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
        }

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
              and not s.get("calibrating") and case != "PAUSED"):
            self._logged_risk = (risk, case)
            if risk == "WAITING":
                title = "Waiting for seatbelt" if case == "PRE_DRIVE" else "Waiting"
            else:
                title = f"{risk.title()} risk"
                if case not in ("NONE", None):
                    title += " · " + case.replace("_", " ").lower()
            self._append_event("risk", _RISK_LEVEL.get(risk, "info"), title,
                               " / ".join((s.get("messages") or [])[:2]), ts=self._pending_risk[3])
            if risk in ("LOW", "MEDIUM", "HIGH") and case not in ("NONE", None):
                self._alerts[case] = self._alerts.get(case, 0) + 1

        changed, _ = self._changed("paused", bool(s.get("paused")))
        if changed:
            self._append_event("system", "info", "Monitoring paused" if s.get("paused") else "Monitoring resumed")

        links = s.get("links") or {}
        changed, _ = self._changed("voice_seq", links.get("voice_seq"))
        if changed and links.get("voice_last"):
            self._append_event("voice", "info", "Spoken alert", f"“{links['voice_last']}”")
        changed, _ = self._changed("muted", bool(links.get("muted")))
        if changed:
            self._append_event("system", "info", "Voice muted" if links.get("muted") else "Voice unmuted")
        for key, label in (("esp32", "ESP32 link"), ("yolo", "Object detection")):
            changed, old = self._changed(key, links.get(key))
            if changed:
                ok = links.get(key) in ("connected", "running")
                self._append_event("system", "good" if ok else "warning",
                                   f"{label} {links.get(key)}", f"was {old}")

        changed, _ = self._changed("calibrating", bool(s.get("calibrating")))
        if changed:
            if s.get("calibrating"):
                self._append_event("system", "info", "Calibration started",
                                   "look straight at the camera, eyes open, mouth closed")
            else:
                b = s.get("baseline") or {}
                self._append_event("system", "good", "Calibration complete",
                                   f"EAR {b.get('ear', 0):.3f} · MAR {b.get('mar', 0):.3f}")

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

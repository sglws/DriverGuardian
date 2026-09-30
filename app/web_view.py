"""
web_view.py
-----------
The monitoring dashboard: a web page served by the app itself, for watching
the Pi remotely (a laptop, phone, or several testers at once) without
screen sharing. Open http://<pi-hostname>.local:8080 (e.g. http://pi5.local:8080).

Why not remote desktop (Pi Connect / VNC): those re-encode the Pi's whole
desktop as video in software (the Pi 5 has no hardware video encoder), and
a camera window that changes every frame is the worst case for them - the
remote desktop lags and stutters. The dashboard streams only the app's own
annotated frames as JPEGs (MJPEG), encoded only while someone is watching,
plus small JSON updates.

Endpoints
    /                       the dashboard (static files in app/web/)
    /stream.mjpg            live annotated video
    /snapshot.jpg           latest frame
    /api/state              current state (risk, driver signals, detections, health)
    /api/history?since=T    time series sampled every WEB_HISTORY_INTERVAL_SEC
    /api/events?since=ID    event log (risk changes, voice prompts, link changes...)
    POST /api/recalibrate   restart driver calibration

Threads here only move bytes and encode JPEGs (OpenCV releases the GIL
while encoding); none of them ever fork() a process - the hazard behind
this project's earlier freeze. The main loop only hands over a frame
reference and a status dict a few times a second; it never waits on a viewer.
"""

import json
import os
import re
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2

from app import config

_WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
_CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                  ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
_RISK_ORDER = ["WAITING", "SAFE", "LOW", "MEDIUM", "HIGH"]
_RISK_LEVEL = {"HIGH": "critical", "MEDIUM": "serious", "LOW": "warning", "SAFE": "good"}


def _lan_address():
    """Best-guess LAN IP for the startup message (no packet is sent)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


class WebView:
    def __init__(self):
        self.enabled = config.WEB_VIEW_ENABLED
        self._cond = threading.Condition()     # frame/jpeg hand-off and viewer count
        self._data_lock = threading.Lock()     # state/history/events/session
        self._frame = None
        self._frame_seq = 0
        self._jpeg = None
        self._jpeg_seq = 0
        self._viewers = 0
        self._last_handoff = 0.0
        self._commands = []

        self._state = {}
        self._state_at = 0.0
        self._history = deque(maxlen=int(config.WEB_HISTORY_SEC / config.WEB_HISTORY_INTERVAL_SEC))
        self._last_sample = 0.0
        self._events = deque(maxlen=300)
        self._event_id = 0
        self._started_mono = time.monotonic()
        self._started_wall = time.time()
        self._time_in = {r: 0.0 for r in _RISK_ORDER}
        self._alerts = {}
        self._prev = {}                        # previous values, for change detection
        self._pending_risk = None              # (risk, case, since) - debounce for the log
        self._logged_risk = None
        self._last_status = None

        if not self.enabled:
            return
        try:
            self._server = ThreadingHTTPServer((config.WEB_VIEW_HOST, config.WEB_VIEW_PORT), self._handler())
        except OSError as e:
            print(f"[web] dashboard unavailable - port {config.WEB_VIEW_PORT}: {e}")
            self.enabled = False
            return
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        threading.Thread(target=self._encoder, daemon=True).start()
        host = socket.gethostname().removesuffix(".local")
        print(f"[web] Dashboard: http://{host}.local:{config.WEB_VIEW_PORT}  "
              f"(or http://{_lan_address()}:{config.WEB_VIEW_PORT})")
        self.log("system", "info", "Monitoring started")

    # ------------------------------------------------------------------
    # Called from the main loop - all instant
    # ------------------------------------------------------------------

    def wants_frame(self, now: float) -> bool:
        """True when someone is watching and the next stream frame is due."""
        return (self.enabled and self._viewers > 0
                and now - self._last_handoff >= 1.0 / config.WEB_VIEW_FPS)

    def wants_status(self, now: float) -> bool:
        return self.enabled and (self._last_status is None
                                 or now - self._last_status >= config.WEB_STATUS_INTERVAL_SEC)

    def publish(self, frame, now: float):
        """Hand over the finished, annotated frame. The main loop never draws
        on this array afterwards (each loop iteration gets a new frame)."""
        self._last_handoff = now
        with self._cond:
            self._frame = frame
            self._frame_seq += 1
            self._cond.notify_all()

    def set_status(self, state: dict, now: float):
        """Latest full state from the main loop (a few times a second)."""
        if not self.enabled:
            return
        with self._data_lock:
            if self._last_status is not None and self._prev.get("risk") in self._time_in:
                self._time_in[self._prev["risk"]] += now - self._last_status
            self._last_status = now
            self._detect_events(state, now)
            state["session"] = {
                "started_ts": self._started_wall,
                "uptime_s": now - self._started_mono,
                "time_in": dict(self._time_in),
                "alerts": dict(self._alerts),
            }
            self._state, self._state_at = state, now
            if now - self._last_sample >= config.WEB_HISTORY_INTERVAL_SEC:
                self._last_sample = now
                eyes, mouth, head = state.get("eyes") or {}, state.get("mouth") or {}, state.get("head") or {}
                if not state.get("face_found"):
                    # no face: the app's placeholder EAR/MAR/pose aren't
                    # measurements - leave a gap in the charts instead
                    eyes, mouth, head = {"ear_thr": eyes.get("ear_thr")}, {"mar_thr": mouth.get("mar_thr")}, {}
                self._history.append({
                    "t": round(now, 3), "ts": time.time(),
                    "risk": state.get("risk"), "case": state.get("case"),
                    "ear": eyes.get("ear"), "ear_thr": eyes.get("ear_thr"),
                    "mar": mouth.get("mar"), "mar_thr": mouth.get("mar_thr"),
                    "pitch": head.get("pitch"), "yaw": head.get("yaw"),
                    "fps": (state.get("perf") or {}).get("fps"),
                })

    def log(self, kind: str, level: str, title: str, detail: str = ""):
        """Add an entry to the event log (kind: risk / voice / detect / system;
        level: good / warning / serious / critical / info)."""
        if not self.enabled:
            return
        with self._data_lock:
            self._append_event(kind, level, title, detail)

    def take_command(self):
        """A command from the dashboard ('recalibrate'), or None."""
        return self._commands.pop(0) if self._commands else None

    def close(self):
        if self.enabled:
            self._server.shutdown()

    # ------------------------------------------------------------------
    # Event detection (runs inside set_status, under _data_lock)
    # ------------------------------------------------------------------

    def _append_event(self, kind, level, title, detail="", ts=None):
        self._event_id += 1
        self._events.append({"id": self._event_id, "ts": ts or time.time(), "kind": kind,
                             "level": level, "title": title, "detail": detail})

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
        # flicker doesn't flood the log.
        if self._pending_risk is None or self._pending_risk[:2] != (risk, case):
            self._pending_risk = (risk, case, now, time.time())
        elif (now - self._pending_risk[2] >= 0.5 and self._logged_risk != (risk, case)
              and not s.get("calibrating")):
            self._logged_risk = (risk, case)
            if risk == "WAITING":
                title = "Waiting for seatbelt" if case == "PRE_DRIVE" else "Waiting"
            else:
                title = f"{risk.title()} risk"
                if case not in ("NONE", None):
                    title += " · " + case.replace("_", " ").lower()
            # stamped with when the change began, not when it was confirmed
            self._append_event("risk", _RISK_LEVEL.get(risk, "info"), title,
                               " / ".join((s.get("messages") or [])[:2]), ts=self._pending_risk[3])
            if risk in ("LOW", "MEDIUM", "HIGH") and case not in ("NONE", None):
                self._alerts[case] = self._alerts.get(case, 0) + 1

        links = s.get("links") or {}
        changed, _ = self._changed("voice_seq", links.get("voice_seq"))
        if changed and links.get("voice_last"):
            self._append_event("voice", "info", "Spoken alert", f"“{links['voice_last']}”")
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
        changed, old = self._changed("seatbelt", seatbelt)
        if changed and seatbelt in ("ON", "OFF"):
            self._append_event("detect", "good" if seatbelt == "ON" else "warning",
                               f"Seatbelt {seatbelt.lower()}", "")
        presence = s.get("presence")
        changed, _ = self._changed("presence", presence)
        if changed and presence:
            self._append_event("detect", "good" if presence == "DRIVER_PRESENT" else "critical",
                               presence.replace("_", " ").capitalize(), "")
        throttled = (s.get("system") or {}).get("throttled") or []
        changed, _ = self._changed("throttled", bool(throttled))
        if changed and throttled:
            self._append_event("system", "critical", "CPU throttling", ", ".join(throttled))

    # ------------------------------------------------------------------
    # Background threads
    # ------------------------------------------------------------------

    def _encoder(self):
        seen = 0
        while True:
            with self._cond:
                self._cond.wait_for(lambda: self._frame_seq != seen)
                frame, seen = self._frame, self._frame_seq
            h, w = frame.shape[:2]
            if w > config.WEB_VIEW_WIDTH:
                frame = cv2.resize(frame, (config.WEB_VIEW_WIDTH, round(h * config.WEB_VIEW_WIDTH / w)),
                                   interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, config.WEB_VIEW_JPEG_QUALITY])
            if ok:
                with self._cond:
                    self._jpeg, self._jpeg_seq = buf.tobytes(), self._jpeg_seq + 1
                    self._cond.notify_all()

    def _handler(self):
        view = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):   # keep the console quiet
                pass

            def _send(self, code, ctype, body):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, obj):
                self._send(200, "application/json", json.dumps(obj, separators=(",", ":")).encode())

            def do_GET(self):
                url = urlparse(self.path)
                q = parse_qs(url.query)
                path = url.path
                try:
                    if path in ("/", "/index.html"):
                        self._static("index.html")
                    elif path.startswith("/static/"):
                        self._static(path[len("/static/"):])
                    elif path == "/api/state":
                        with view._data_lock:
                            state, at = dict(view._state), view._state_at
                        state["age_sec"] = (time.monotonic() - at) if at else None
                        state["viewers"] = view._viewers
                        self._json(state)
                    elif path == "/api/history":
                        since = float(q.get("since", ["-1"])[0])
                        with view._data_lock:
                            samples = [p for p in view._history if p["t"] > since]
                        self._json({"samples": samples, "window_sec": config.WEB_HISTORY_SEC,
                                    "now": time.monotonic()})
                    elif path == "/api/events":
                        since = int(q.get("since", ["0"])[0])
                        with view._data_lock:
                            events = [e for e in view._events if e["id"] > since]
                        self._json({"events": events})
                    elif path == "/snapshot.jpg":
                        if view._jpeg is None:
                            self._send(503, "text/plain", b"no frame yet - open the dashboard first")
                        else:
                            self._send(200, "image/jpeg", view._jpeg)
                    elif path == "/stream.mjpg":
                        self._stream()
                    else:
                        self._send(404, "text/plain", b"not found")
                except ValueError:
                    self._send(400, "text/plain", b"bad request")

            def do_POST(self):
                # The custom header makes browsers preflight cross-site requests,
                # which this server never approves - so another website can't
                # trigger actions on the Pi through a visitor's browser.
                if self.headers.get("X-DriverGuardian") != "1":
                    self._send(403, "text/plain", b"forbidden")
                elif urlparse(self.path).path == "/api/recalibrate":
                    view._commands.append("recalibrate")
                    view.log("system", "info", "Recalibration requested", "from the dashboard")
                    self._json({"ok": True})
                else:
                    self._send(404, "text/plain", b"not found")

            def _static(self, name):
                ext = os.path.splitext(name)[1]
                if not re.fullmatch(r"[\w.-]+", name) or ext not in _CONTENT_TYPES:
                    self._send(404, "text/plain", b"not found")
                    return
                try:
                    with open(os.path.join(_WEB_DIR, name), "rb") as f:
                        body = f.read()
                except OSError:
                    self._send(404, "text/plain", b"not found")
                    return
                self._send(200, _CONTENT_TYPES[ext], body)

            def _stream(self):
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with view._cond:
                    view._viewers += 1
                seen = 0   # _jpeg_seq starts at 0 with no frame: wait for the first real one
                try:
                    while True:
                        with view._cond:
                            if not view._cond.wait_for(lambda: view._jpeg_seq != seen, timeout=5.0):
                                continue   # nothing new (app calibrating/stalled) - keep the connection
                            jpeg, seen = view._jpeg, view._jpeg_seq
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                         b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n")
                        self.wfile.write(jpeg)
                        self.wfile.write(b"\r\n")
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass   # viewer closed the page
                finally:
                    with view._cond:
                        view._viewers -= 1

        return Handler

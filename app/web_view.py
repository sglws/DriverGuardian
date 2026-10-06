"""
web_view.py
-----------
The monitoring dashboard: a web page served by the app itself, for watching
and controlling the Pi remotely (a laptop, phone, or several testers at
once) without screen sharing. Open http://<pi-hostname>.local:8080.

Why not remote desktop (Pi Connect / VNC): those re-encode the Pi's whole
desktop as video in software (the Pi 5 has no hardware video encoder), and
a camera window that changes every frame is the worst case for them - the
remote desktop lags and stutters. The dashboard streams only the app's own
annotated frames as JPEGs (MJPEG), encoded only while someone is watching,
plus small JSON updates.

Endpoints
    /                               the dashboard (static files in app/web/)
    /stream.mjpg, /snapshot.jpg     live video / latest frame
    /api/state                      current state (risk, signals, health, session)
    /api/history?since=T            live time series (last WEB_HISTORY_SEC)
    /api/events?since=ID            live event log
    /api/sessions                   saved sessions (history database)
    /api/sessions/ID                one session: summary, events, timeline
    /api/sessions/ID/samples.csv    its timeline as CSV
    /api/sessions/ID/events.csv     its events as CSV
    POST /api/control {action}      pause | resume | new_session | stop |
                                    recalibrate | mute | unmute
    POST /api/marker {text}         add a marker to the current session
    POST /api/sessions/ID {label, notes}   rename / annotate a session
    DELETE /api/sessions/ID         delete a saved session

Threads here only move bytes, read the database and encode JPEGs; none of
them ever fork() a process - the hazard behind this project's earlier
freeze. Commands are queued for the main loop, which applies them.
"""

import csv
import io
import json
import os
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2

from app import config

_WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
_CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                  ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
_ACTIONS = {"pause", "resume", "new_session", "stop", "recalibrate", "mute", "unmute"}


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
    def __init__(self, recorder, store=None):
        self.recorder, self.store = recorder, store
        self.enabled = config.WEB_VIEW_ENABLED
        self._cond = threading.Condition()     # frame/jpeg hand-off and viewer count
        self._frame = None
        self._frame_seq = 0
        self._jpeg = None
        self._jpeg_seq = 0
        self._viewers = 0
        self._last_handoff = 0.0
        self._commands = []
        self._cmd_lock = threading.Lock()
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

    # ---- called from the main loop (all instant) ----

    def wants_frame(self, now: float) -> bool:
        """True when someone is watching and the next stream frame is due."""
        return (self.enabled and self._viewers > 0
                and now - self._last_handoff >= 1.0 / config.WEB_VIEW_FPS)

    def publish(self, frame, now: float):
        """Hand over the finished, annotated frame. The main loop never draws
        on this array afterwards (each loop iteration gets a new frame)."""
        self._last_handoff = now
        with self._cond:
            self._frame = frame
            self._frame_seq += 1
            self._cond.notify_all()

    def take_commands(self):
        """Commands queued by the dashboard since the last call."""
        with self._cmd_lock:
            cmds, self._commands = self._commands, []
        return cmds

    @property
    def viewers(self):
        return self._viewers

    def close(self):
        if self.enabled:
            self._server.shutdown()

    # ---- background threads ----

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

            def _send(self, code, ctype, body, extra_headers=None):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for k, v in (extra_headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _json(self, obj, code=200):
                self._send(code, "application/json", json.dumps(obj, separators=(",", ":")).encode())

            def _error(self, code, msg):
                self._json({"ok": False, "error": msg}, code)

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                if n > 8192:
                    raise ValueError("request too large")
                raw = self.rfile.read(n) if n else b""
                return json.loads(raw or b"{}")

            def _trusted(self):
                # The custom header makes browsers preflight cross-site requests,
                # which this server never approves - so another website can't
                # trigger actions on the Pi through a visitor's browser.
                return self.headers.get("X-DriverGuardian") == "1"

            # ---------------------------------------------------- GET
            def do_GET(self):
                url = urlparse(self.path)
                q = parse_qs(url.query)
                path = url.path
                try:
                    if path in ("/", "/index.html"):
                        return self._static("index.html")
                    if path.startswith("/static/"):
                        return self._static(path[len("/static/"):])
                    if path == "/api/state":
                        state, at = view.recorder.snapshot()
                        state["age_sec"] = (time.monotonic() - at) if at else None
                        state["viewers"] = view._viewers
                        state["history_keep"] = config.SESSION_HISTORY_KEEP
                        return self._json(state)
                    if path == "/api/history":
                        return self._json({"samples": view.recorder.history_since(float(q.get("since", ["-1"])[0])),
                                           "window_sec": config.WEB_HISTORY_SEC})
                    if path == "/api/events":
                        return self._json({"events": view.recorder.events_since(int(q.get("since", ["0"])[0]))})
                    if path == "/snapshot.jpg":
                        if view._jpeg is None:
                            return self._error(503, "no frame yet - open the dashboard first")
                        return self._send(200, "image/jpeg", view._jpeg)
                    if path == "/stream.mjpg":
                        return self._stream()
                    m = re.fullmatch(r"/api/sessions(?:/(\d+)(?:/(samples|events)\.csv)?)?", path)
                    if m:
                        return self._sessions_get(m.group(1), m.group(2))
                    self._error(404, "not found")
                except ValueError:
                    self._error(400, "bad request")

            def _sessions_get(self, sid, csv_kind):
                if view.store is None:
                    return self._error(503, "session history is disabled")
                current = view.recorder.session_id
                if sid is None:
                    rows = view.store.list_sessions()
                    for r in rows:
                        r["status"] = "live" if r["id"] == current else "complete" if r["ended_ts"] else "interrupted"
                        if r["id"] == current:
                            r["summary"] = view.recorder.live_summary()
                    return self._json({"sessions": rows, "keep": config.SESSION_HISTORY_KEEP})
                s = view.store.get_session(int(sid))
                if s is None:
                    return self._error(404, "session not found")
                s["status"] = "live" if s["id"] == current else "complete" if s["ended_ts"] else "interrupted"
                if s["id"] == current:
                    s["summary"] = view.recorder.live_summary()
                if csv_kind is None:
                    return self._json(s)
                rows = s["samples"] if csv_kind == "samples" else s["events"]
                buf = io.StringIO()
                if rows:
                    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
                    w.writeheader()
                    for r in rows:
                        r = dict(r)
                        r["time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"]))
                        w.writerow({k: r[k] for k in rows[0].keys()} | ({"ts": r["time"]}))
                safe = re.sub(r"[^\w.-]+", "_", s["label"] or f"session_{sid}")
                self._send(200, "text/csv; charset=utf-8", buf.getvalue().encode(),
                           {"Content-Disposition": f'attachment; filename="{safe}_{csv_kind}.csv"'})

            # ---------------------------------------------------- POST / DELETE
            def do_POST(self):
                if not self._trusted():
                    return self._error(403, "forbidden")
                path = urlparse(self.path).path
                try:
                    body = self._body()
                except (ValueError, json.JSONDecodeError):
                    return self._error(400, "bad request")
                if path == "/api/control":
                    action = body.get("action")
                    if action not in _ACTIONS:
                        return self._error(400, "unknown action")
                    with view._cmd_lock:
                        view._commands.append((action, body))
                    return self._json({"ok": True})
                if path == "/api/marker":
                    view.recorder.mark(str(body.get("text") or "Marker"))
                    return self._json({"ok": True})
                m = re.fullmatch(r"/api/sessions/(\d+)", path)
                if m and view.store is not None:
                    sid = int(m.group(1))
                    label, notes = body.get("label"), body.get("notes")
                    if sid == view.recorder.session_id and label:
                        view.recorder.set_label(str(label))
                    fields = {}
                    if label and sid != view.recorder.session_id:
                        fields["label"] = str(label).strip()[:120]
                    if notes is not None:
                        fields["notes"] = str(notes)[:2000]
                    if fields:
                        view.store.update_session(sid, **fields)
                    return self._json({"ok": True})
                self._error(404, "not found")

            def do_DELETE(self):
                if not self._trusted():
                    return self._error(403, "forbidden")
                m = re.fullmatch(r"/api/sessions/(\d+)", urlparse(self.path).path)
                if not m or view.store is None:
                    return self._error(404, "not found")
                if int(m.group(1)) == view.recorder.session_id:
                    return self._error(409, "this session is still running - end it first")
                view.store.delete_session(int(m.group(1)))
                self._json({"ok": True})

            # ---------------------------------------------------- helpers
            def _static(self, name):
                ext = os.path.splitext(name)[1]
                if not re.fullmatch(r"[\w.-]+", name) or ext not in _CONTENT_TYPES:
                    return self._error(404, "not found")
                try:
                    with open(os.path.join(_WEB_DIR, name), "rb") as f:
                        body = f.read()
                except OSError:
                    return self._error(404, "not found")
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

"""
web_view.py
-----------
Live view of the running app in any web browser - the way to watch the Pi
remotely (from a laptop, phone, or several testers at once) without
screen sharing.

Why not remote desktop (Pi Connect / VNC): those re-encode the Pi's whole
desktop as video in software (the Pi 5 has no hardware video encoder), and
a camera window that changes every frame is the worst case for them - the
remote desktop lags and stutters. This streams only the app's own annotated
frames as JPEGs (MJPEG), encoded only while someone is actually watching,
and needs no window on the Pi at all.

    http://<pi-hostname>.local:8080/            live page
    http://<pi-hostname>.local:8080/stream.mjpg raw video stream
    http://<pi-hostname>.local:8080/status      current state as JSON
    http://<pi-hostname>.local:8080/snapshot.jpg the latest frame

Threads here only move bytes and encode JPEGs (OpenCV releases the GIL
while encoding); none of them ever fork() a process - the hazard behind
this project's earlier freeze. The main loop only hands over a frame
reference and a status dict; it never waits on a viewer.
"""

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

from app import config

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DriverGuardian live</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; background: #0f1113; color: #e8e6e3; font: 15px/1.4 system-ui, sans-serif; }
  header { display: flex; flex-wrap: wrap; gap: 12px 20px; align-items: center; padding: 12px 16px; }
  h1 { font-size: 16px; margin: 0; font-weight: 600; }
  .risk { padding: 4px 12px; border-radius: 6px; font-weight: 700; letter-spacing: .03em; background: #3a3d41; }
  .risk.SAFE { background: #1e7a3c; } .risk.LOW { background: #b8a200; color: #111; }
  .risk.MEDIUM { background: #d97a00; color: #111; } .risk.HIGH { background: #c62828; }
  .muted { color: #9a9894; }
  main { padding: 0 16px 16px; }
  img { display: block; width: 100%; max-width: 1280px; border-radius: 8px; background: #000; }
  #msgs { margin: 10px 0 0; color: #cfcdca; min-height: 1.4em; }
  button { background: #2b2f33; color: #e8e6e3; border: 1px solid #4a4e53; border-radius: 6px;
           padding: 6px 12px; font: inherit; cursor: pointer; }
  button:hover { background: #363a3f; }
</style></head>
<body>
<header>
  <h1>DriverGuardian</h1>
  <span id="risk" class="risk">-</span>
  <span>case <b id="case">-</b></span>
  <span class="muted"><span id="fps">-</span> FPS</span>
  <span class="muted" id="age"></span>
  <button id="recal" title="Recalibrate the driver baseline">Recalibrate</button>
</header>
<main>
  <img src="/stream.mjpg" alt="live camera view">
  <div id="msgs"></div>
</main>
<script>
async function poll() {
  try {
    const s = await (await fetch('/status', {cache: 'no-store'})).json();
    const r = document.getElementById('risk');
    r.textContent = s.risk || '-'; r.className = 'risk ' + (s.risk || '');
    document.getElementById('case').textContent = s.case || '-';
    document.getElementById('fps').textContent = s.fps != null ? s.fps.toFixed(1) : '-';
    document.getElementById('msgs').textContent = (s.messages || []).join('  /  ');
    document.getElementById('age').textContent = s.age_sec > 2 ? 'no update for ' + s.age_sec.toFixed(0) + ' s' : '';
  } catch (e) { document.getElementById('age').textContent = 'app not reachable'; }
}
setInterval(poll, 500); poll();
document.getElementById('recal').onclick = async () => {
  await fetch('/recalibrate', {method: 'POST'});
};
</script>
</body></html>
"""


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
        self._cond = threading.Condition()
        self._frame = None          # latest annotated frame handed over by the main loop
        self._frame_seq = 0
        self._jpeg = None           # latest encoded JPEG
        self._jpeg_seq = 0
        self._status = {}
        self._status_at = 0.0
        self._viewers = 0
        self._last_handoff = 0.0
        self._commands = []
        if not self.enabled:
            return
        try:
            self._server = ThreadingHTTPServer((config.WEB_VIEW_HOST, config.WEB_VIEW_PORT), self._handler())
        except OSError as e:
            print(f"[web] live view unavailable - port {config.WEB_VIEW_PORT}: {e}")
            self.enabled = False
            return
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        threading.Thread(target=self._encoder, daemon=True).start()
        host = socket.gethostname().removesuffix(".local")
        print(f"[web] Live view: http://{host}.local:{config.WEB_VIEW_PORT}  "
              f"(or http://{_lan_address()}:{config.WEB_VIEW_PORT})")

    # ---- called from the main loop (all instant) ----

    def wants_frame(self, now: float) -> bool:
        """True when someone is watching and the next stream frame is due."""
        return (self.enabled and self._viewers > 0
                and now - self._last_handoff >= 1.0 / config.WEB_VIEW_FPS)

    def publish(self, frame, now: float):
        """Hand over the finished, annotated frame. The main loop must not
        draw on this array afterwards (it doesn't: every loop iteration
        gets a new frame from the camera)."""
        self._last_handoff = now
        with self._cond:
            self._frame = frame
            self._frame_seq += 1
            self._cond.notify_all()

    def set_status(self, status: dict):
        if self.enabled:
            self._status = status
            self._status_at = time.monotonic()

    def take_command(self):
        """A command from the page ('recalibrate'), or None."""
        return self._commands.pop(0) if self._commands else None

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

            def _send(self, code, ctype, body):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    self._send(200, "text/html; charset=utf-8", _PAGE.encode())
                elif self.path == "/status":
                    status = dict(view._status)
                    status["age_sec"] = time.monotonic() - view._status_at if view._status_at else None
                    self._send(200, "application/json", json.dumps(status).encode())
                elif self.path == "/snapshot.jpg":
                    if view._jpeg is None:
                        self._send(503, "text/plain", b"no frame yet - open the live page first")
                    else:
                        self._send(200, "image/jpeg", view._jpeg)
                elif self.path == "/stream.mjpg":
                    self._stream()
                else:
                    self._send(404, "text/plain", b"not found")

            def do_POST(self):
                if self.path == "/recalibrate":
                    view._commands.append("recalibrate")
                    self._send(200, "text/plain", b"ok")
                else:
                    self._send(404, "text/plain", b"not found")

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

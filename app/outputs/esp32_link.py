"""Bluetooth link to the ESP32 vehicle controller (RFCOMM serial).

Sends "RISK,CASE" lines and reads the "TEL,..." telemetry lines back.
Reconnects in small non-blocking steps, so a missing ESP32 never pauses the main loop.
"""

import errno
import os
import select
import socket
import subprocess
import sys
import time

try:
    _BLUETOOTH_SOCKETS_AVAILABLE = hasattr(socket, "AF_BLUETOOTH") and hasattr(socket, "BTPROTO_RFCOMM")
except Exception:
    _BLUETOOTH_SOCKETS_AVAILABLE = False

from app import config

if not _BLUETOOTH_SOCKETS_AVAILABLE:
    print("[ESP32] this Python has no Bluetooth socket support - the ESP32 link is disabled")


class Esp32Link:
    """Raw Bluetooth RFCOMM socket to the ESP32."""

    IDLE, PRIMING, SETTLING, CONNECTING = "IDLE", "PRIMING", "SETTLING", "CONNECTING"
    PRIME_TIMEOUT_SEC = 10.0
    SETTLE_SEC = 2.0
    CONNECT_ABANDON_SEC = 20.0
    STALL_RECONNECT_SEC = 6.0

    def __init__(self):
        self._sock = None
        self._consecutive_send_failures = 0
        self._connect_failures = 0
        self._reported_down = False
        self._stalled_since = None
        self._state = self.IDLE
        self._next_attempt_at = 0.0
        self._deadline = 0.0
        self._proc = None
        self._pending = None
        self._rx = b""
        self.telemetry, self.telemetry_at = None, None

    def _prime_start(self, now):
        """bluetoothctl connect first: a cold RFCOMM connect() to the ESP32 fails ("Invalid exchange")."""
        if not sys.platform.startswith("linux"):
            self._connect_start(now)
            return
        try:
            self._proc = subprocess.Popen(
                ["bluetoothctl", "connect", config.ESP32_MAC_ADDRESS],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True,
            )
        except Exception as e:
            print(f"[ESP32] bluetoothctl connect failed to run: {e}")
            self._proc = None
        self._state = self.PRIMING
        self._deadline = now + self.PRIME_TIMEOUT_SEC

    def _connect_start(self, now):
        try:
            sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                                 socket.BTPROTO_RFCOMM)
            sock.setblocking(False)
            err = sock.connect_ex((config.ESP32_MAC_ADDRESS, config.ESP32_RFCOMM_PORT))
        except Exception as e:
            self._fail(now, e)
            return
        if err == 0:
            self._connected(sock)
        elif err in (errno.EINPROGRESS, errno.EAGAIN, errno.EALREADY):
            self._pending = sock
            self._state = self.CONNECTING
            self._deadline = now + self.CONNECT_ABANDON_SEC
        else:
            sock.close()
            self._fail(now, OSError(err, os.strerror(err)))

    def _connected(self, sock):
        sock.setblocking(False)
        self._sock = sock
        self._pending = None
        self._state = self.IDLE
        self._consecutive_send_failures = 0
        self._connect_failures = 0
        self._reported_down = False
        self._stalled_since = None
        print(f"[ESP32] Connected to {config.ESP32_MAC_ADDRESS}")

    def _fail(self, now, reason):
        if self._pending is not None:
            try:
                self._pending.close()
            except Exception:
                pass
            self._pending = None
        self._state = self.IDLE
        self._connect_failures += 1
        cooldown = min(config.ESP32_RECONNECT_COOLDOWN_SEC * 2 ** (self._connect_failures - 1),
                       config.ESP32_RECONNECT_MAX_COOLDOWN_SEC)
        self._next_attempt_at = now + cooldown
        print(f"[ESP32] Could not connect to {config.ESP32_MAC_ADDRESS}: {reason} "
              f"(will retry in {cooldown:.0f}s)")

    def _advance(self, now):
        """One step of the reconnect state machine (IDLE -> PRIMING -> SETTLING -> CONNECTING). Never blocks."""
        if self._state == self.IDLE:
            if now >= self._next_attempt_at:
                self._prime_start(now)
        elif self._state == self.PRIMING:
            done = self._proc is None or self._proc.poll() is not None
            if not done and now < self._deadline:
                return
            if self._proc is not None:
                if not done:
                    self._proc.kill()
                    try:
                        self._proc.wait(timeout=0.5)
                    except Exception:
                        pass
                    print("[ESP32] bluetoothctl connect timed out")
                else:
                    out = (self._proc.communicate()[0] or "").strip()
                    print(f"[ESP32] bluetoothctl connect: {out}")
                self._proc = None
            self._state = self.SETTLING
            self._deadline = now + self.SETTLE_SEC
        elif self._state == self.SETTLING:
            if now >= self._deadline:
                self._connect_start(now)
        elif self._state == self.CONNECTING:
            try:
                _, writable, errored = select.select([], [self._pending], [self._pending], 0)
            except Exception as e:
                self._fail(now, e)
                return
            if not writable and not errored:
                if now >= self._deadline:
                    self._fail(now, f"connect still pending after {self.CONNECT_ABANDON_SEC:.0f}s")
                return
            err = self._pending.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err:
                self._fail(now, OSError(err, os.strerror(err)))
            else:
                self._connected(self._pending)

    def _ensure_open(self):
        if self._sock is not None:
            return self._sock
        if not config.ESP32_LINK_ENABLED or not _BLUETOOTH_SOCKETS_AVAILABLE:
            return None
        self._advance(time.monotonic())
        return self._sock

    @property
    def status(self) -> str:
        if not config.ESP32_LINK_ENABLED:
            return "disabled"
        if not _BLUETOOTH_SOCKETS_AVAILABLE:
            return "unsupported"
        return "connected" if self._sock is not None else "searching"

    def poll_rx(self, now: float):
        """Read whatever telemetry the ESP32 has sent. Never blocks."""
        sock = self._sock
        if sock is None:
            return
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    return
                self._rx += chunk
        except (BlockingIOError, InterruptedError):
            pass
        except OSError:
            return
        *lines, self._rx = self._rx.split(b"\n")
        self._rx = self._rx[-256:]
        for raw in lines[-5:]:
            t = _parse_telemetry(raw)
            if t is not None:
                self.telemetry, self.telemetry_at = t, now

    def send(self, risk_name: str, case: str):
        line = f"{risk_name},{case}\n"
        sock = self._ensure_open()
        if sock is None:
            if not self._reported_down:
                self._reported_down = True
                print("[ESP32] Not connected - reconnecting in the background; "
                      "monitoring and voice alerts continue on the Pi")
            return
        try:
            sock.send(line.encode("ascii", errors="replace"))
            self._consecutive_send_failures = 0
            self._stalled_since = None
        except BlockingIOError:   # link congested: drop this line, reconnect if it lasts
            now = time.monotonic()
            if self._stalled_since is None:
                self._stalled_since = now
            elif now - self._stalled_since >= self.STALL_RECONNECT_SEC:
                print(f"[ESP32] Link stalled for {self.STALL_RECONNECT_SEC:.0f}s, reconnecting")
                try:
                    sock.close()
                except Exception:
                    pass
                self._sock = None
                self._stalled_since = None
        except Exception as e:
            self._consecutive_send_failures += 1
            if self._consecutive_send_failures >= config.ESP32_SEND_FAILURE_TOLERANCE:
                print(f"[ESP32] Send failed {self._consecutive_send_failures}x in a row, "
                      f"reconnecting: {e}")
                try:
                    sock.close()
                except Exception:
                    pass
                self._sock = None
                self._consecutive_send_failures = 0
            else:
                print(f"[ESP32] Send failed ({self._consecutive_send_failures}/"
                      f"{config.ESP32_SEND_FAILURE_TOLERANCE}, not reconnecting yet): {e}")


def _parse_telemetry(raw: bytes):
    """TEL,risk,leftPWM,rightPWM,basePWM,frontCm,rearCm,irFront,irRear,estop,linkFailed,pulloverMs"""
    parts = raw.decode("ascii", errors="replace").strip().split(",")
    if len(parts) != 12 or parts[0] != "TEL":
        return None
    try:
        left, right, base = int(parts[2]), int(parts[3]), int(parts[4])
        front, rear = float(parts[5]), float(parts[6])
        ir_front, ir_rear, estop, link_failed = (int(v) for v in parts[7:11])
        pullover_ms = int(parts[11])
    except ValueError:
        return None
    dist = lambda d: None if d >= 900 else round(d, 1)   # 999 = nothing in range
    return {
        "risk": parts[1], "left_pwm": left, "right_pwm": right, "base_pwm": base,
        "speed_pct": round(100 * (left + right) / (2 * base)) if base else None,
        "front_cm": dist(front), "rear_cm": dist(rear),
        "ir_front": bool(ir_front), "ir_rear": bool(ir_rear),
        "estop": {0: None, 1: "obstacle", 2: "edge"}.get(estop, "unknown"),
        "link_failed": bool(link_failed), "pullover_s": round(pullover_ms / 1000, 1),
    }

"""
alerts.py
---------
Phase 14 deliverable: alert dispatch by risk tier + case, driving the
ESP32 over Bluetooth (RFCOMM/SPP - see esp32/DriverGuardian_ESP32 and the
README's pairing instructions).

Wire protocol (newline-terminated ASCII, matches the ESP32 sketch):
    RISK,CASE\n
e.g. "HIGH,SLEEP\n", "MEDIUM,SEATBELT\n", "LOW,PHONE\n", "SAFE,NONE\n"

This is sent on a fixed interval (ESP32_SEND_INTERVAL_SEC), not just on
change, so it doubles as a heartbeat: the ESP32 firmware treats a gap
longer than its own timeout as a Bluetooth link failure and fails safe
independently (flowchart Case 8: "Bluetooth Failure -> HIGH -> Safe stop
mode") - it can't wait around for a Pi that may itself be the problem.

Connects with a raw AF_BLUETOOTH/BTPROTO_RFCOMM socket straight to the
ESP32's MAC address (config.ESP32_MAC_ADDRESS) - no `rfcomm bind`/
`/dev/rfcommX` device file involved. This process owns the one connection
itself; don't also run a separate always-on script/systemd service
connecting to the same ESP32, since classic Bluetooth SPP only accepts
one client at a time and the two would fight over that single slot.
"""

import errno
import os
import select
import shutil
import socket
import subprocess
import sys
import time

from app.risk_engine import Risk

try:
    _BLUETOOTH_SOCKETS_AVAILABLE = hasattr(socket, "AF_BLUETOOTH") and hasattr(socket, "BTPROTO_RFCOMM")
except Exception:
    _BLUETOOTH_SOCKETS_AVAILABLE = False

if not _BLUETOOTH_SOCKETS_AVAILABLE:
    # Without this, a missing AF_BLUETOOTH/BTPROTO_RFCOMM silently made
    # every send() a no-op forever - "(not connected)" with no explanation
    # anywhere, indistinguishable from a real connection failure.
    print("[ESP32] This Python has no AF_BLUETOOTH/BTPROTO_RFCOMM socket support - "
          "the ESP32 link is disabled. (Expected on Windows; on Linux, this usually "
          "means bluez/python3-dev support wasn't compiled in.)")

from app import config


class Voice:
    """Spoken alerts that never block the video loop.

    Speaks by launching the OS speech program (espeak-ng/espeak on the Pi,
    `say` on macOS) with subprocess.Popen and NOT waiting for it - each
    call returns in about a millisecond while the audio plays in its own
    process. The previous pyttsx3 runAndWait() froze frame processing for
    the full length of every sentence (1-3 s), and at HIGH risk - which
    re-speaks every HIGH_RISK_VOICE_REPEAT_SEC - that stalled monitoring
    for a large share of exactly the time it matters most, and would break
    the <= 1 s classification-gap requirement on its own.

    Deliberately NOT a thread, and the spawn happens on the main thread:
    fork() from a background thread while Qt is loaded (cv2.imshow()) is
    the proven root cause of this project's whole-system freeze (git
    bisect) - see Esp32Link below for the same rule.

    One utterance at a time: a new alert interrupts the one still playing
    (the newest risk is the relevant one); a HIGH repeat is skipped while
    the previous repeat is still being spoken rather than piling up.
    """

    def __init__(self):
        self._cmd = None
        for name, args in (("espeak-ng", ["-s", "165"]), ("espeak", ["-s", "165"]), ("say", [])):
            path = shutil.which(name)
            if path:
                self._cmd = [path, *args]
                break
        self._proc = None
        if config.VOICE_ALERTS_ENABLED and self._cmd is None:
            print("[VOICE] No speech program found - alerts will only be printed. "
                  "On the Pi: sudo apt install espeak-ng")

    def busy(self) -> bool:
        # poll() also reaps a finished process, so no zombies accumulate.
        return self._proc is not None and self._proc.poll() is None

    def say(self, text: str, interrupt: bool = True):
        if not config.VOICE_ALERTS_ENABLED:
            print(f"[VOICE] (disabled) {text}")
            return
        print(f"[VOICE] {text}")
        if self._cmd is None:
            return
        if self.busy():
            if not interrupt:
                return
            self._proc.kill()
            self._proc.wait()   # already killed: returns immediately
        try:
            self._proc = subprocess.Popen(
                [*self._cmd, text], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"[VOICE] speech failed: {e}")
            self._proc = None

    def close(self):
        if self.busy():
            self._proc.kill()


class Esp32Link:
    """Raw Bluetooth RFCOMM socket link to the ESP32. Connects lazily,
    retries on a cooldown after a failure, and never raises - a
    disconnected ESP32 shouldn't crash driver monitoring.

    Reconnecting is a NON-BLOCKING state machine driven from the main loop:
    each call to send() advances it by at most one cheap step and returns
    immediately. A reconnect used to run as one blocking sequence on a
    single frame - `bluetoothctl connect` (up to 10 s), a 2 s settle sleep,
    then a connect() with no timeout - which could freeze frame processing
    for well over 5 s. That broke the >= 0.2 Hz risk-classification
    requirement (a classification at least every 5 s) whenever the ESP32
    dropped out, exactly the moment monitoring matters most.

        IDLE -> PRIMING -> SETTLING -> CONNECTING -> connected
          ^________ on any failure, after RECONNECT_COOLDOWN _______|

    Deliberately NOT a background thread. This class was threaded twice in
    this project's history and both times caused a severe freeze (proven by
    git bisect the second time): spawning a subprocess via fork() from a
    background thread while Qt is loaded (cv2.imshow()) is a real Linux
    hazard. Everything here - including the bluetoothctl spawn - still
    happens on the main thread, exactly as before; it just no longer waits.
    """

    IDLE, PRIMING, SETTLING, CONNECTING = "IDLE", "PRIMING", "SETTLING", "CONNECTING"
    PRIME_TIMEOUT_SEC = 10.0    # give up on bluetoothctl after this long
    SETTLE_SEC = 2.0            # let the ACL link come up before connecting
    # Upper bound on a connect() that is still in progress. Deliberately
    # generous, and it only ABANDONS a stuck attempt - it never shortens a
    # live handshake the way a socket timeout did (a 2 s connect timeout was
    # confirmed to cut the RFCOMM handshake mid-negotiation, surfacing as
    # "[Errno 52] Invalid exchange").
    CONNECT_ABANDON_SEC = 20.0

    def __init__(self):
        self._sock = None
        self._consecutive_send_failures = 0
        self._state = self.IDLE
        self._next_attempt_at = 0.0
        self._deadline = 0.0
        self._proc = None
        self._pending = None

    def _prime_start(self, now):
        """A cold raw RFCOMM connect() to this ESP32 reliably fails with
        `[Errno 52] Invalid exchange` - confirmed on this hardware - unless
        the underlying ACL (baseband) link is already up. `bluetoothctl
        connect` establishes it even though it reports a spurious "profile
        unavailable" error for SPP (bluetoothd has no generic serial-port
        profile handler - harmless, we only need the link up). It returns
        as soon as the request is *sent*, hence the settle step after it.

        bluetoothctl is Linux/BlueZ-only, so off Linux priming is skipped
        and we go straight to connecting.
        """
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
        # Back to blocking with a timeout for the actual sends. 0.2 s was
        # too aggressive for this link and a single slow send (the very first
        # one after connecting) tore the connection down over a transient
        # hiccup - see _consecutive_send_failures in send() for the rest.
        sock.settimeout(2.0)
        self._sock = sock
        self._pending = None
        self._state = self.IDLE
        self._consecutive_send_failures = 0
        print(f"[ESP32] Connected to {config.ESP32_MAC_ADDRESS}")

    def _fail(self, now, reason):
        if self._pending is not None:
            try:
                self._pending.close()
            except Exception:
                pass
            self._pending = None
        self._state = self.IDLE
        # Cooldown measured from when the attempt ENDED, not when it began -
        # otherwise an attempt longer than the cooldown would immediately
        # trigger the next one (the cause of an earlier ~0.1 FPS regression).
        self._next_attempt_at = now + config.ESP32_RECONNECT_COOLDOWN_SEC
        print(f"[ESP32] Could not connect to {config.ESP32_MAC_ADDRESS}: {reason} "
              f"(will retry in {config.ESP32_RECONNECT_COOLDOWN_SEC:.0f}s)")

    def _advance(self, now):
        """Move the reconnect state machine forward by at most one step.
        Never blocks: every wait is a timestamp comparison or a zero-timeout
        poll/select."""
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
                        self._proc.wait(timeout=0.5)   # reap it; SIGKILL exits near-instantly
                    except Exception:
                        pass
                    print("[ESP32] bluetoothctl connect timed out")
                else:
                    out = (self._proc.communicate()[0] or "").strip()   # already exited: returns at once
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

    def send(self, risk_name: str, case: str):
        line = f"{risk_name},{case}\n"
        sock = self._ensure_open()
        if sock is None:
            print(f"[ESP32 -> ] (not connected) {line.strip()}")
            return
        try:
            sock.send(line.encode("ascii", errors="replace"))
            self._consecutive_send_failures = 0
        except Exception as e:
            self._consecutive_send_failures += 1
            # A single slow/dropped send on a Bluetooth Classic link is
            # often just a transient hiccup, not a real disconnection -
            # confirmed on this hardware: tearing the connection down on
            # the very first failure caused a reconnect that hit the ESP32
            # mid-teardown ("Device or resource busy"), which then got
            # stuck ("Host is down") because the old connection hadn't
            # been released cleanly on its end yet. Only reconnect once
            # failures are clearly sustained, not a one-off blip.
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


class AlertSystem:
    """Tracks last-fired risk tier so voice/dashboard don't spam every
    frame, and rate-limits the ESP32 link to ESP32_SEND_INTERVAL_SEC
    (its own heartbeat cadence - see Esp32Link/esp32/ sketch docstrings).
    """

    def __init__(self):
        self._last_risk = None
        self._last_high_speak = 0.0
        self._last_esp32_send = 0.0
        self._esp32 = Esp32Link()
        self._voice = Voice()

    def dispatch(self, risk: Risk, messages: list[str], case: str = "NONE"):
        now = time.time()

        # Only re-fire voice/dashboard alerts on a risk-tier change to avoid
        # spamming the driver every single frame at 20-30 FPS.
        changed = risk != self._last_risk
        self._last_risk = risk

        if risk == Risk.LOW:
            if changed:
                self._voice.say(messages[0] if messages else "Please stay focused.")
        elif risk == Risk.MEDIUM:
            if changed:
                self._voice.say(messages[0] if messages else "Warning: please pay attention.")
        elif risk == Risk.HIGH:
            # Deliberately NOT gated by `changed` alone like LOW/MEDIUM -
            # HIGH re-speaks continuously as a sustained alarm for as long
            # as the danger persists, rate-limited to HIGH_RISK_VOICE_REPEAT_SEC.
            # A repeat never cuts off the previous one mid-sentence
            # (interrupt=False); a fresh escalation to HIGH does.
            if changed or now - self._last_high_speak >= config.HIGH_RISK_VOICE_REPEAT_SEC:
                self._last_high_speak = now
                self._voice.say(messages[0] if messages else "Warning. Please respond immediately.",
                                interrupt=changed)
            if changed:
                print("[DASHBOARD] HIGH RISK ALERT -", " / ".join(messages))

        # The ESP32 gets every risk tier, including SAFE - it needs the
        # continuous stream to tell "still SAFE" apart from "link down".
        if now - self._last_esp32_send >= config.ESP32_SEND_INTERVAL_SEC:
            self._last_esp32_send = now
            self._esp32.send(risk.name, case)

    def close(self):
        self._voice.close()

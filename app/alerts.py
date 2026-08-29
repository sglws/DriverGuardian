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

import socket
import subprocess
import sys
import threading
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

try:
    import pyttsx3
    _tts_engine = pyttsx3.init()
    _TTS_AVAILABLE = True
except Exception:
    _TTS_AVAILABLE = False

from app import config


_speak_lock = threading.Lock()


def _speak_blocking(text: str):
    if _TTS_AVAILABLE:
        try:
            _tts_engine.say(text)
            _tts_engine.runAndWait()
            return
        except Exception:
            pass
    print(f"[VOICE] {text}")


def _speak(text: str):
    """Fires the actual (potentially multi-second) TTS playback on its own
    thread. Confirmed on hardware: called synchronously, a sustained
    HIGH-risk spell (which re-speaks periodically - see
    AlertSystem.dispatch) froze the whole video loop for the length of
    every warning, several real seconds each time - rate-limiting alone
    (below) only reduced how often that happened, not the freeze itself.

    Unlike Esp32Link, there's no shared state here for another thread to
    read back or a cooldown timer whose ordering can be gotten wrong -
    fire-and-forget, nothing downstream depends on when/whether it
    finishes - so this doesn't reopen the class of bug threading caused
    elsewhere in this app. Skips starting a new utterance if one is
    already playing rather than overlapping/queuing them, since pyttsx3's
    engine isn't meant to be driven by concurrent say()/runAndWait() calls
    - the caller already rate-limits how often this is invoked, so a
    skipped call just means the driver hears the current warning finish
    rather than two garbled ones on top of each other.
    """
    if not config.VOICE_ALERTS_ENABLED:
        print(f"[VOICE] (disabled) {text}")
        return
    if _speak_lock.locked():
        return

    def _run():
        with _speak_lock:
            _speak_blocking(text)

    threading.Thread(target=_run, daemon=True).start()


class Esp32Link:
    """Raw Bluetooth RFCOMM socket link to the ESP32. Connects lazily,
    retries on a cooldown after a failure rather than blocking on every
    frame, and never raises - a disconnected ESP32 shouldn't crash driver
    monitoring.

    Runs entirely on its own background thread. A reconnect attempt
    (bluetoothctl priming + a 2s settle + a blocking socket connect()) can
    legitimately take several real seconds when the ESP32 is unreachable
    (confirmed on Windows: a failed connect() alone can take multiple
    seconds to time out) - even properly cooldown-gated (see
    _last_attempt below), a still-synchronous version freezes frame
    processing for that long *every time* it fires, which is a real,
    recurring stutter, not a one-off.

    This is a deliberate, narrow exception to this app's general "no
    background threads" rule (see YoloWorker's removal), not a reversal
    of it: unlike YOLO inference, this thread is I/O-bound (waiting on a
    socket/subprocess), not CPU-bound - it spends nearly all its time
    asleep or blocked on the network, so it doesn't compete with NCNN for
    CPU cores the way a compute-heavy worker thread did. And unlike the
    original threaded version of this class, the main thread here never
    reads any state back out of this object mid-frame (set_state() is
    fire-and-forget, same as _speak()) - so there's no equivalent of the
    cooldown-ordering bug that caused the original 0.1 FPS regression;
    _last_attempt is still stamped *after* the attempt completes purely
    for correctness (an attempt that outlasts the cooldown shouldn't
    immediately trigger another one), not because anything on the main
    thread depends on that ordering anymore.
    """

    def __init__(self):
        self._sock = None
        self._last_attempt = 0.0
        self._consecutive_send_failures = 0
        self._lock = threading.Lock()
        self._pending_risk = "SAFE"
        self._pending_case = "NONE"
        self._stop = False
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def set_state(self, risk_name: str, case: str):
        """Called from the main video loop every frame - instant,
        thread-safe, never touches the network. Just records the latest
        desired state for the background worker to pick up."""
        with self._lock:
            self._pending_risk = risk_name
            self._pending_case = case

    def close(self):
        self._stop = True

    def _worker(self):
        while not self._stop:
            with self._lock:
                risk_name, case = self._pending_risk, self._pending_case
            self._send_once(risk_name, case)
            time.sleep(config.ESP32_SEND_INTERVAL_SEC)

    def _prime_acl_link(self):
        """A cold raw RFCOMM socket connect() to this ESP32 reliably fails
        with `[Errno 52] Invalid exchange` - confirmed on this hardware -
        unless the underlying ACL (baseband) link is already up.
        `bluetoothctl connect` establishes that link even though it
        reports a spurious "profile unavailable" error for SPP (bluetoothd
        has no generic serial-port profile handler registered - harmless,
        we don't need it to succeed, just to bring the link up).

        `bluetoothctl connect <MAC>` run as a one-shot command returns as
        soon as the connect request is *sent*, not once the link is
        actually up (unlike watching it interactively, where you naturally
        wait to see "Connected: yes" before doing anything else) - so a
        short sleep after it is needed to let the link actually settle
        before the raw socket connect below. Best effort throughout:
        failures/timeouts here are logged but not fatal, the raw socket
        connect right after is the real attempt.

        bluetoothctl is a Linux/BlueZ tool - it doesn't exist on Windows,
        so on a dev machine this always fails instantly, but the 2s settle
        sleep below used to run anyway regardless, purely wasted (measured:
        ~270ms/frame average, dominating the whole frame budget, from one
        reconnect attempt landing in a profiling window). Skipped entirely
        off Linux since neither step does anything meaningful there.
        """
        if not sys.platform.startswith("linux"):
            return
        try:
            result = subprocess.run(
                ["bluetoothctl", "connect", config.ESP32_MAC_ADDRESS],
                capture_output=True, timeout=10, text=True,
            )
            print(f"[ESP32] bluetoothctl connect: {result.stdout.strip() or result.stderr.strip()}")
        except Exception as e:
            print(f"[ESP32] bluetoothctl connect failed to run: {e}")
        time.sleep(2.0)  # let the ACL link actually settle before the raw socket connect

    def _ensure_open(self):
        if self._sock is not None:
            return self._sock
        if not _BLUETOOTH_SOCKETS_AVAILABLE:
            return None

        now = time.time()
        if now - self._last_attempt < config.ESP32_RECONNECT_COOLDOWN_SEC:
            return None

        self._prime_acl_link()

        try:
            sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            # No timeout for connect() itself: a Classic Bluetooth RFCOMM
            # handshake can legitimately take a few seconds, especially
            # right after _prime_acl_link() above. This call blocks the
            # frame it's called from, but only during the rare reconnect
            # attempt, not steady-state.
            sock.connect((config.ESP32_MAC_ADDRESS, config.ESP32_RFCOMM_PORT))
            # 0.2s here was too aggressive for this link and a single slow
            # send (confirmed: the very first one, right after connecting)
            # tore the whole connection down over a transient hiccup - see
            # _consecutive_send_failures below for the other half of this fix.
            sock.settimeout(2.0)
            self._sock = sock
            self._consecutive_send_failures = 0
            print(f"[ESP32] Connected to {config.ESP32_MAC_ADDRESS}")
        except Exception as e:
            print(f"[ESP32] Could not connect to {config.ESP32_MAC_ADDRESS}: {e} "
                  f"(will retry in {config.ESP32_RECONNECT_COOLDOWN_SEC:.0f}s)")
            self._sock = None
        finally:
            # Stamped *after* the blocking connect attempt above, not
            # before - see the class docstring for why that ordering
            # matters (it's what makes the cooldown actually cooldown).
            self._last_attempt = time.time()
        return self._sock

    def _send_once(self, risk_name: str, case: str):
        """Runs on the background worker thread only - see _worker()."""
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
    frame. The ESP32 link paces its own sends on its own background
    thread (ESP32_SEND_INTERVAL_SEC) - dispatch() just hands it the
    latest state every frame, which is instant and never blocks.
    """

    def __init__(self):
        self._last_risk = None
        self._last_high_speak = 0.0
        self._esp32 = Esp32Link()

    def close(self):
        self._esp32.close()

    def dispatch(self, risk: Risk, messages: list[str], case: str = "NONE"):
        now = time.time()

        # Only re-fire voice/dashboard alerts on a risk-tier change to avoid
        # spamming the driver every single frame at 20-30 FPS.
        changed = risk != self._last_risk
        self._last_risk = risk

        if risk == Risk.LOW:
            if changed:
                _speak(messages[0] if messages else "Please stay focused.")
        elif risk == Risk.MEDIUM:
            if changed:
                _speak(messages[0] if messages else "Warning: please pay attention.")
        elif risk == Risk.HIGH:
            # Deliberately NOT gated by `changed` alone like LOW/MEDIUM -
            # HIGH re-speaks continuously as a sustained alarm for as long
            # as the danger persists. But _speak() blocks the video loop
            # for the length of the utterance, so it's rate-limited to
            # HIGH_RISK_VOICE_REPEAT_SEC instead of firing every frame -
            # still a repeating alarm, just not one that stalls frame
            # processing faster than it can finish speaking.
            if changed or now - self._last_high_speak >= config.HIGH_RISK_VOICE_REPEAT_SEC:
                self._last_high_speak = now
                _speak(messages[0] if messages else "Warning. Please respond immediately.")
            if changed:
                print("[DASHBOARD] HIGH RISK ALERT -", " / ".join(messages))

        # The ESP32 gets every risk tier, including SAFE - it needs the
        # continuous stream to tell "still SAFE" apart from "link down".
        self._esp32.set_state(risk.name, case)

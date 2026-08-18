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
"""

import time

from app.risk_engine import Risk

try:
    import serial
    _PYSERIAL_AVAILABLE = True
except ImportError:
    _PYSERIAL_AVAILABLE = False

try:
    import pyttsx3
    _tts_engine = pyttsx3.init()
    _TTS_AVAILABLE = True
except Exception:
    _TTS_AVAILABLE = False

from app import config


def _speak(text: str):
    if _TTS_AVAILABLE:
        try:
            _tts_engine.say(text)
            _tts_engine.runAndWait()
        except Exception:
            print(f"[VOICE] {text}")
    else:
        print(f"[VOICE] {text}")


class Esp32Link:
    """Bluetooth RFCOMM serial link to the ESP32. Opens lazily, retries on
    a cooldown after a failure rather than blocking the main loop, and
    never raises - a disconnected ESP32 shouldn't crash driver monitoring.
    """

    def __init__(self):
        self._serial = None
        self._last_attempt = 0.0

    def _ensure_open(self):
        if self._serial is not None:
            return self._serial
        if not _PYSERIAL_AVAILABLE:
            return None

        now = time.time()
        if now - self._last_attempt < config.ESP32_RECONNECT_COOLDOWN_SEC:
            return None
        self._last_attempt = now

        try:
            self._serial = serial.Serial(config.ESP32_SERIAL_PORT, config.ESP32_BAUD_RATE, timeout=0.2)
            print(f"[ESP32] Connected on {config.ESP32_SERIAL_PORT}")
        except Exception as e:
            print(f"[ESP32] Could not open {config.ESP32_SERIAL_PORT}: {e} "
                  f"(will retry in {config.ESP32_RECONNECT_COOLDOWN_SEC:.0f}s)")
            self._serial = None
        return self._serial

    def send(self, risk_name: str, case: str):
        line = f"{risk_name},{case}\n"
        ser = self._ensure_open()
        if ser is None:
            print(f"[ESP32 -> ] (not connected) {line.strip()}")
            return
        try:
            ser.write(line.encode("ascii", errors="replace"))
        except Exception as e:
            print(f"[ESP32] Write failed, will reconnect: {e}")
            try:
                ser.close()
            except Exception:
                pass
            self._serial = None


class AlertSystem:
    """Tracks last-fired risk tier so voice/dashboard don't spam every
    frame, and rate-limits the ESP32 link to ESP32_SEND_INTERVAL_SEC
    (its own heartbeat cadence - see Esp32Link/esp32/ sketch docstrings).
    """

    def __init__(self):
        self._last_risk = None
        self._last_esp32_send = 0.0
        self._esp32 = Esp32Link()

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
            _speak(messages[0] if messages else "Warning. Please respond immediately.")
            if changed:
                print("[DASHBOARD] HIGH RISK ALERT -", " / ".join(messages))

        # The ESP32 gets every risk tier, including SAFE - it needs the
        # continuous stream to tell "still SAFE" apart from "link down".
        if now - self._last_esp32_send >= config.ESP32_SEND_INTERVAL_SEC:
            self._last_esp32_send = now
            self._esp32.send(risk.name, case)

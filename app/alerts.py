"""
alerts.py
---------
Phase 14 deliverable: alert dispatch by risk tier.

Currently implemented as console/print stubs plus optional local text-to-
speech (pyttsx3, if installed). Swap `_send_to_esp32` for real
serial/Bluetooth/WiFi writes once your ESP32 hardware link is ready -
that's the only function that needs to change to go from "demo mode" to
"real hardware mode".
"""

from app.risk_engine import Risk

try:
    import pyttsx3
    _tts_engine = pyttsx3.init()
    _TTS_AVAILABLE = True
except Exception:
    _TTS_AVAILABLE = False


def _speak(text: str):
    if _TTS_AVAILABLE:
        try:
            _tts_engine.say(text)
            _tts_engine.runAndWait()
        except Exception:
            print(f"[VOICE] {text}")
    else:
        print(f"[VOICE] {text}")


def _send_to_esp32(command: str):
    """TODO: replace with real serial/BLE/WiFi write to your ESP32.
    e.g. esp32_serial.write(command.encode())"""
    print(f"[ESP32 -> ] {command}")


class AlertSystem:
    """Tracks last-fired risk tier so we don't spam voice/buzzer every frame."""

    def __init__(self):
        self._last_risk = None

    def dispatch(self, risk: Risk, messages: list[str]):
        # Only re-fire alerts on a risk-tier change to avoid spamming
        # the driver every single frame at 20-30 FPS.
        changed = risk != self._last_risk
        self._last_risk = risk

        if risk == Risk.SAFE:
            return

        if risk == Risk.LOW:
            if changed:
                _speak(messages[0] if messages else "Please stay focused.")

        elif risk == Risk.MEDIUM:
            if changed:
                _speak(messages[0] if messages else "Warning: please pay attention.")
                _send_to_esp32("LED_AMBER_ON")

        elif risk == Risk.HIGH:
            _speak(messages[0] if messages else "Warning. Please respond immediately.")
            _send_to_esp32("BUZZER_ON")
            _send_to_esp32("SEAT_VIBRATION_ON")
            _send_to_esp32("HAZARD_LIGHTS_ON")
            if changed:
                print("[DASHBOARD] HIGH RISK ALERT -", " / ".join(messages))

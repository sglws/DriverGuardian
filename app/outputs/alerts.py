"""Sends each frame's risk decision to the voice alerts and, every 0.3 s, to the ESP32.

The regular ESP32 message is also its heartbeat: 6 s of silence makes the car pull over.
"""

import time

from app import config
from app.outputs.esp32_link import Esp32Link
from app.outputs.voice import VoiceAlerts
from app.risk.risk_engine import Risk


class AlertSystem:
    def __init__(self):
        self._last_risk = None
        self._last_esp32_send = 0.0
        self._esp32 = Esp32Link()
        self._voice = VoiceAlerts()

    def dispatch(self, risk: Risk, messages: list[str], case: str = "NONE"):
        now = time.monotonic()

        if risk == Risk.HIGH and self._last_risk != Risk.HIGH:
            print("[DASHBOARD] HIGH RISK ALERT -", " / ".join(messages))
        self._last_risk = risk

        self._voice.update(risk, case, now)
        self._esp32.poll_rx(now)

        if now - self._last_esp32_send >= config.ESP32_SEND_INTERVAL_SEC:
            self._last_esp32_send = now
            self._esp32.send(risk.name, case)

    def health(self, now: float) -> dict:
        """Link and voice status for the dashboard."""
        v = self._voice
        return {
            "esp32": self._esp32.status,
            "voice": v.status,
            "voice_last": v.last_text,
            "voice_seq": v.seq,
            "muted": v.muted,
            "voice_last_age": (now - v.last_at) if v.last_at is not None else None,
            "vehicle": self.vehicle(now),
        }

    def vehicle(self, now: float):
        """Latest ESP32 telemetry, or None if none arrived in the last 2 s."""
        e = self._esp32
        if e.telemetry is None or e.status != "connected" or now - e.telemetry_at > 2.0:
            return None
        return {**e.telemetry, "age_s": round(now - e.telemetry_at, 2)}

    def say(self, key: str, now: float):
        """Speak a test instruction (see voice.TEST_PROMPTS)."""
        self._voice.say(key, now)

    def set_muted(self, muted: bool):
        self._voice.muted = muted
        if muted:
            self._voice.close()

    def close(self):
        self._voice.close()

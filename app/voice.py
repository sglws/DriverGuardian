"""
voice.py
--------
Spoken driver alerts.

Design
  * One short, fixed phrase per situation (PROMPTS below - the only place
    wording lives). The risk engine's `case` code picks the phrase; the
    risk tier picks how it's delivered.
  * Every prompt is a chime followed by the phrase. Warnings (LOW/MEDIUM)
    get a soft two-note chime; critical alerts (HIGH) get an urgent
    three-pulse tone. The lead-in also wakes Bluetooth speakers, which
    otherwise clip the first syllable.
  * Prompts are rendered ONCE to WAV files (cached under assets/voice_cache,
    re-rendered only when a phrase or the TTS engine changes) and
    loudness-normalized, so every alert plays at the same level with zero
    synthesis delay at runtime. Engine: Piper (natural neural voice, if
    VOICE_PIPER_VOICE is installed) > espeak-ng > macOS `say`.
  * Playback is a separate player process that is never waited on, started
    from the main thread - no threads (fork() from a background thread
    while Qt is loaded is this project's proven freeze; see alerts.py).

Pacing (what keeps it calm instead of noisy)
  * A warning must be the active case for VOICE_CONFIRM_SEC before it is
    spoken, so a one-frame detection never talks.
  * The same warning is repeated only after its own repeat interval
    (PROMPTS), e.g. phone every 8 s, yawning once a minute.
  * At least VOICE_MIN_GAP_SEC of silence between any two prompts.
  * One prompt at a time. A new critical alert interrupts a warning; nothing
    interrupts a critical alert. Critical alerts repeat every
    VOICE_CRITICAL_REPEAT_SEC while the danger lasts.
  * Nothing is said when things return to normal.
"""

import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import wave

import numpy as np

from app import config
from app.risk_engine import Risk

# case code -> (phrase, repeat interval in seconds while that case stays active)
PROMPTS = {
    "PRE_DRIVE":      ("Please put on your seatbelt. The drive will start once it is on.", 20.0),
    "SEATBELT":       ("Your seatbelt is off. Please put it back on.", 15.0),
    "PHONE":          ("Please put your phone away.", 8.0),
    "CONSUMPTION":    ("Please keep your focus on the road.", 15.0),
    "TURN":           ("Please keep your eyes on the road.", 6.0),
    "LEAN":           ("Please sit upright.", 6.0),
    "MICROSLEEP":     ("Stay alert.", 5.0),
    "YAWN":           ("You seem tired. Consider taking a break.", 60.0),
    "SLEEP":          ("Wake up. Stopping the vehicle.", 0.0),
    "LEAN_PROLONGED": ("No response. Stopping the vehicle.", 0.0),
    "TURN_PROLONGED": ("No response. Stopping the vehicle.", 0.0),
    "BLOCKED":        ("Camera blocked. Stopping the vehicle.", 0.0),
    "ABSENT":         ("Driver not detected. Stopping the vehicle.", 0.0),
}
ALIASES = {"PHONE_REPEAT": "PHONE", "CONSUMPTION_REPEAT": "CONSUMPTION"}

_RENDER_VERSION = "1"   # bump to force re-rendering after changing the audio design
_CACHE_DIR = os.path.join(config.BASE_DIR, "assets", "voice_cache")


# ---------------------------------------------------------------- rendering

def _tone(rate, freq, dur, amp, decay):
    t = np.arange(int(rate * dur)) / rate
    wave_ = np.sin(2 * math.pi * freq * t) + 0.25 * np.sin(2 * math.pi * 2 * freq * t)
    env = np.minimum(1.0, t / 0.005) * np.exp(-t * decay)   # 5 ms attack, no click
    return amp * wave_ * env / 1.25


def _silence(rate, dur):
    return np.zeros(int(rate * dur))


def _chime(rate, critical):
    if critical:   # three short, bright pulses - unmistakably urgent, not harsh
        pulse = _tone(rate, 1568.0, 0.11, 0.55, 14.0)
        return np.concatenate([pulse, _silence(rate, 0.07)] * 2 + [pulse])
    # soft ascending two-note chime (A5 -> E6)
    return np.concatenate([_tone(rate, 880.0, 0.16, 0.40, 9.0), _tone(rate, 1318.5, 0.30, 0.40, 7.0)])


def _find(*names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def _piper_model():
    """Path of the configured Piper voice model, or None if not installed.
    VOICE_PIPER_VOICE is a voice name (looked up in models/piper/) or a path."""
    voice = getattr(config, "VOICE_PIPER_VOICE", "")
    if not voice or importlib.util.find_spec("piper") is None:
        return None
    path = voice if voice.endswith(".onnx") else os.path.join(config.MODELS_DIR, "piper", voice + ".onnx")
    return path if os.path.exists(path) and os.path.exists(path + ".json") else None


def _tts_engine():
    """(engine_name, render) - render(jobs) writes each [(text, wav_path)].
    The engine name includes the voice so the prompt cache re-renders when
    the voice changes. Preference: Piper (natural) > espeak-ng > macOS say."""
    model = _piper_model()
    if model:
        def render(jobs):
            # one process for every phrase: the voice model loads only once
            subprocess.run([sys.executable, "-m", "app.piper_render", model],
                           input=json.dumps(jobs), text=True, capture_output=True,
                           timeout=300, check=True, cwd=config.BASE_DIR)
        return f"piper:{os.path.basename(model)}", render
    espeak = _find("espeak-ng", "espeak")
    if espeak:
        def render(jobs):
            for text, out in jobs:
                subprocess.run([espeak, "-v", "en-us", "-s", "150", "-w", out, text],
                               capture_output=True, timeout=30, check=True)
        return "espeak:en-us", render
    say = _find("say")
    if say:
        def render(jobs):
            for text, out in jobs:   # macOS system voice
                subprocess.run([say, "-o", out, "--data-format=LEI16@22050", text],
                               capture_output=True, timeout=30, check=True)
        return "say", render
    return None, None


def _read_wav(path):
    with wave.open(path, "rb") as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16 if width == 2 else np.uint8)
    data = data.astype(np.float64)
    if width == 1:
        data = (data - 128) * 256
    if ch > 1:
        data = data[::ch]
    return rate, data / 32768.0


def _clean_speech(raw_path):
    """Speech for one phrase: trimmed of the engine's own leading/trailing
    silence and peak-normalized, so every prompt plays at the same level."""
    rate, speech = _read_wav(raw_path)
    idx = np.flatnonzero(np.abs(speech) > 0.01)
    if idx.size:
        speech = speech[idx[0]:idx[-1] + 1]
    peak = np.max(np.abs(speech)) if speech.size else 0.0
    if peak > 0:
        speech = speech * (0.80 / peak)
    return rate, speech


def _write_prompt(rate, speech, critical, out_path):
    audio = np.concatenate([
        _silence(rate, 0.25),          # lets a sleeping Bluetooth speaker wake up
        _chime(rate, critical),
        _silence(rate, 0.12),
        speech,
        _silence(rate, 0.10),
    ])
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- playback

class VoiceAlerts:
    def __init__(self):
        self._files = {}          # (case, critical) -> wav path
        self._player = None
        self._proc = None
        self._playing_critical = False
        self._ended_at = -1e9
        self._last_start = {}     # (case, critical) -> monotonic time
        self._candidate, self._candidate_since = None, 0.0
        self.last_text, self.last_at, self.seq = None, None, 0   # last prompt (for the dashboard)
        if not config.VOICE_ALERTS_ENABLED:
            print("[VOICE] disabled (VOICE_ALERTS_ENABLED = False)")
            return

        if sys.platform == "darwin":
            player = _find("afplay")
            self._player = [player] if player else None
        else:
            player = _find("pw-play", "paplay", "aplay")
            self._player = ([player, "-q"] if player and player.endswith("aplay") else [player]) if player else None
        engine, render = _tts_engine()
        if not self._player or not engine:
            print(f"[VOICE] unavailable - "
                  f"{'no audio player' if not self._player else 'no TTS engine'} found. "
                  f"On the Pi: sudo apt install espeak-ng pipewire-bin")
            return

        os.makedirs(_CACHE_DIR, exist_ok=True)
        todo = []   # (case, text, {critical: path}) still missing from the cache
        for case, (text, _) in PROMPTS.items():
            paths = {}
            for critical in (False, True):
                tag = hashlib.sha1(f"{_RENDER_VERSION}|{engine}|{critical}|{text}".encode()).hexdigest()[:10]
                paths[critical] = os.path.join(_CACHE_DIR, f"{case.lower()}_{'crit' if critical else 'warn'}_{tag}.wav")
            if any(not os.path.exists(path) for path in paths.values()):
                todo.append((case, text, paths))
            else:
                for critical, path in paths.items():
                    self._files[(case, critical)] = path
        if todo:
            print(f"[VOICE] rendering {len(todo)} phrases with {engine} (first start / voice change)...")
            raws = [os.path.join(_CACHE_DIR, f"_raw_{i}.wav") for i in range(len(todo))]
            try:
                render([(text, raw) for (_, text, _), raw in zip(todo, raws)])
            except Exception as e:
                detail = getattr(e, "stderr", "") or ""
                print(f"[VOICE] rendering failed ({engine}): {e} {detail[-300:]}")
            for (case, text, paths), raw in zip(todo, raws):
                try:
                    rate, speech = _clean_speech(raw)
                    for critical, path in paths.items():
                        _write_prompt(rate, speech, critical, path)
                        self._files[(case, critical)] = path
                except Exception as e:
                    print(f"[VOICE] could not render '{text}': {e}")
                finally:
                    if os.path.exists(raw):
                        os.remove(raw)
        print(f"[VOICE] ready - {len(self._files) // 2} of {len(PROMPTS)} phrases ({engine}, "
              f"{len(todo)} newly rendered), playing via {os.path.basename(self._player[0])}")

    def _busy(self, now):
        if self._proc is not None and self._proc.poll() is not None:   # poll() also reaps it
            self._proc = None
            self._ended_at = now
        return self._proc is not None

    def _play(self, key, critical, now):
        if self._busy(now):
            self._proc.kill()
            self._proc.wait()
        try:
            self._proc = subprocess.Popen([*self._player, self._files[key]], stdin=subprocess.DEVNULL,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[VOICE] playback failed: {e}")
            self._proc = None
            return
        self._playing_critical = critical
        self._last_start[key] = now

    def update(self, risk: Risk, case: str, now: float):
        """Call every frame with the current risk tier and case code."""
        busy = self._busy(now)   # every frame, so the end of a prompt is timed exactly
        case = ALIASES.get(case, case)
        if risk == Risk.SAFE or case not in PROMPTS:
            self._candidate = None
            return
        critical = risk == Risk.HIGH
        key = (case, critical)

        if key != self._candidate:
            self._candidate, self._candidate_since = key, now
        if not critical and now - self._candidate_since < config.VOICE_CONFIRM_SEC:
            return

        repeat = config.VOICE_CRITICAL_REPEAT_SEC if critical else PROMPTS[case][1]
        if now - self._last_start.get(key, -1e9) < repeat:
            return

        if busy:
            if not (critical and not self._playing_critical):   # only an escalation may cut in
                return
        elif now - self._ended_at < config.VOICE_MIN_GAP_SEC:
            return

        print(f"[VOICE] {PROMPTS[case][0]}")
        self.last_text, self.last_at, self.seq = PROMPTS[case][0], now, self.seq + 1
        if key in self._files:
            self._play(key, critical, now)
        else:
            self._last_start[key] = now   # printed only (voice disabled or unavailable)

    @property
    def status(self) -> str:
        if not config.VOICE_ALERTS_ENABLED:
            return "off"
        return "on" if self._files else "unavailable"

    def close(self):
        if self._proc is not None and self._proc.poll() is None:
            self._proc.kill()

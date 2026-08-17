"""
drowsiness.py
-------------
Phase 5 deliverable: blink detection (count + duration).
Phase 6 deliverable: drowsiness rules -> Safe / Drowsy / Sleeping.
Also: yawn detection (Mouth Aspect Ratio threshold + duration).

Thresholds are RELATIVE to a calibrated baseline EAR/MAR (see main.py's
calibration step), not fixed absolute numbers - this keeps detection
accurate across different drivers, cameras, and lighting.
"""

from collections import deque
from enum import Enum

from app import config


class DrowsinessLevel(Enum):
    SAFE = 0
    DROWSY = 1
    SLEEPING = 2


class DrowsinessDetector:
    def __init__(self):
        self.baseline_ear = 0.30  # overwritten by calibration
        self.eyes_closed_since = None
        self.blink_timestamps = deque()
        self.prev_eye_closed = False
        self.total_blinks = 0

        self.baseline_mar = 0.5  # overwritten by calibration
        self.mouth_open_since = None
        self.yawn_timestamps = deque()
        self.prev_mouth_open = False
        self.total_yawns = 0

    def set_baseline(self, baseline_ear: float):
        self.baseline_ear = baseline_ear

    def set_mouth_baseline(self, baseline_mar: float):
        self.baseline_mar = baseline_mar

    @property
    def closed_threshold(self) -> float:
        return self.baseline_ear * config.EAR_CLOSED_RATIO

    @property
    def open_mouth_threshold(self) -> float:
        return self.baseline_mar * config.MAR_YAWN_RATIO

    def update(self, smoothed_ear: float, now: float, pitch_delta: float = 0.0,
               smoothed_mar: float = 0.0):
        """Call once per frame. Returns a dict with the current eye/drowsiness state.

        `pitch_delta` is the calibrated head-pitch offset (positive = looking
        down). Beyond EAR_SUPPRESS_PITCH_DOWN_DEG the eyelid landmarks
        foreshorten and EAR becomes unreliable, so a low EAR reading in that
        band is treated as "looking down", not "eyes closed" - a driver
        glancing at the dashboard/phone shouldn't register as drowsy.
        Genuine leaning is still caught independently by the head-pose Case 2
        logic in risk_engine.py.

        `smoothed_mar` is the calibrated-relative Mouth Aspect Ratio (see
        mouth_tracker.py) - a sustained wide-open mouth (a yawn, not talking
        or a brief word) is tracked here but deliberately kept OUT of
        `level` below: a yawn alone is a much weaker signal than sustained
        eye closure or a high blink rate (people yawn from boredom/habit,
        not just fatigue), so it's scored as its own LOW-risk contribution
        in risk_engine.py rather than being folded into DROWSY/MEDIUM.
        """
        looking_down = pitch_delta >= config.EAR_SUPPRESS_PITCH_DOWN_DEG
        eye_closed = smoothed_ear < self.closed_threshold and not looking_down

        # ---- Blink detection (Phase 5): count a blink on the closed->open edge ----
        if self.prev_eye_closed and not eye_closed:
            self.blink_timestamps.append(now)
            self.total_blinks += 1
        self.prev_eye_closed = eye_closed

        while self.blink_timestamps and now - self.blink_timestamps[0] > config.BLINK_WINDOW_SEC:
            self.blink_timestamps.popleft()

        # ---- Closure duration tracking ----
        if eye_closed:
            if self.eyes_closed_since is None:
                self.eyes_closed_since = now
            closed_elapsed = now - self.eyes_closed_since
        else:
            self.eyes_closed_since = None
            closed_elapsed = 0.0

        # ---- Yawn detection: mouth-open duration tracking, mirrors eye closure ----
        mouth_open = smoothed_mar > self.open_mouth_threshold
        if mouth_open:
            if self.mouth_open_since is None:
                self.mouth_open_since = now
            open_elapsed = now - self.mouth_open_since
        else:
            if (self.prev_mouth_open and self.mouth_open_since is not None
                    and now - self.mouth_open_since >= config.YAWN_MIN_DURATION_SEC):
                self.yawn_timestamps.append(now)
                self.total_yawns += 1
            self.mouth_open_since = None
            open_elapsed = 0.0
        self.prev_mouth_open = mouth_open

        while self.yawn_timestamps and now - self.yawn_timestamps[0] > config.YAWN_RATE_WINDOW_SEC:
            self.yawn_timestamps.popleft()

        is_yawning = mouth_open and open_elapsed >= config.YAWN_MIN_DURATION_SEC
        yawn_rate = len(self.yawn_timestamps)

        # ---- Phase 6 rules (eye/blink only - yawning is scored separately, see above) ----
        blink_rate = len(self.blink_timestamps)
        if closed_elapsed >= config.EAR_SLEEPING_SEC:
            level = DrowsinessLevel.SLEEPING
        elif closed_elapsed >= config.EAR_MICROSLEEP_SEC or blink_rate >= config.BLINK_RATE_DROWSY_THRESHOLD:
            level = DrowsinessLevel.DROWSY
        else:
            level = DrowsinessLevel.SAFE

        return {
            "eye_closed": eye_closed,
            "closed_elapsed": closed_elapsed,
            "blink_rate": blink_rate,
            "total_blinks": self.total_blinks,
            "level": level,
            "looking_down": looking_down,
            "mouth_open": mouth_open,
            "open_elapsed": open_elapsed,
            "is_yawning": is_yawning,
            "yawn_rate": yawn_rate,
            "total_yawns": self.total_yawns,
        }

    def reset(self):
        self.eyes_closed_since = None
        self.blink_timestamps.clear()
        self.prev_eye_closed = False
        self.mouth_open_since = None
        self.yawn_timestamps.clear()
        self.prev_mouth_open = False

"""Eye closure, blinks, microsleep, sleep and yawns from the smoothed EAR and MAR."""

from collections import deque
from enum import Enum

from app import config


class DrowsinessLevel(Enum):
    SAFE = 0
    DROWSY = 1
    SLEEPING = 2


class DrowsinessDetector:
    def __init__(self):
        self.baseline_ear = 0.30
        self.eyes_closed_since = None
        self.blink_timestamps = deque()
        self.prev_eye_closed = False
        self.total_blinks = 0

        self.baseline_mar = 0.5
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
        return max(self.baseline_mar * config.MAR_YAWN_RATIO, config.MAR_OPEN_MIN)

    def update(self, smoothed_ear: float, now: float, pitch_delta: float = 0.0,
               smoothed_mar: float = 0.0, face_found: bool = True):
        """Once per frame; returns the eye and mouth state."""
        # Looking down makes open eyes look closed, so closure is ignored then.
        looking_down = pitch_delta >= config.EAR_SUPPRESS_PITCH_DOWN_DEG
        eye_closed = face_found and smoothed_ear < self.closed_threshold and not looking_down

        if self.prev_eye_closed and not eye_closed and face_found:
            self.blink_timestamps.append(now)
            self.total_blinks += 1
        self.prev_eye_closed = eye_closed

        while self.blink_timestamps and now - self.blink_timestamps[0] > config.BLINK_WINDOW_SEC:
            self.blink_timestamps.popleft()

        if eye_closed:
            if self.eyes_closed_since is None:
                self.eyes_closed_since = now
            closed_elapsed = now - self.eyes_closed_since
        else:
            self.eyes_closed_since = None
            closed_elapsed = 0.0

        mouth_open = face_found and smoothed_mar > self.open_mouth_threshold
        if mouth_open:
            if self.mouth_open_since is None:
                self.mouth_open_since = now
            open_elapsed = now - self.mouth_open_since
        else:
            if (face_found and self.prev_mouth_open and self.mouth_open_since is not None
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

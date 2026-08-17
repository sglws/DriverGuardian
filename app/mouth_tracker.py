"""
mouth_tracker.py
-----------------
Yawn detection support: Mouth Aspect Ratio (MAR) extraction, mirroring
eye_tracker.py's EAR approach.

MAR = |top_lip - bottom_lip| / |left_corner - right_corner|

Uses the same inner-lip landmarks as utils.mouth_roi (61/291 corners,
13/14 top/bottom) for consistency with the rest of the codebase.
"""

from collections import deque
from app import config, utils

MOUTH_LEFT = 61
MOUTH_RIGHT = 291
MOUTH_TOP = 13
MOUTH_BOTTOM = 14


class MouthTracker:
    """Tracks smoothed MAR, mirroring EyeTracker's EAR smoothing."""

    def __init__(self, smoothing_frames: int = config.MAR_SMOOTHING_FRAMES):
        self._history = deque(maxlen=smoothing_frames)

    def update(self, landmarks, w, h) -> float:
        left = (landmarks[MOUTH_LEFT].x * w, landmarks[MOUTH_LEFT].y * h)
        right = (landmarks[MOUTH_RIGHT].x * w, landmarks[MOUTH_RIGHT].y * h)
        top = (landmarks[MOUTH_TOP].x * w, landmarks[MOUTH_TOP].y * h)
        bottom = (landmarks[MOUTH_BOTTOM].x * w, landmarks[MOUTH_BOTTOM].y * h)

        vertical = utils.euclidean(top, bottom)
        horizontal = utils.euclidean(left, right)
        mar = vertical / horizontal if horizontal else 0.0

        self._history.append(mar)
        return sum(self._history) / len(self._history)

    def reset(self):
        self._history.clear()

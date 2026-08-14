"""
eye_tracker.py
--------------
Phase 4 deliverable: eye landmark extraction + Eye Aspect Ratio (EAR).

EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
(Soukupova & Cech, 2016 - standard drowsiness-detection formula)
"""

from collections import deque
from app import config, utils

# Standard MediaPipe Face Mesh eye landmark indices (6-point EAR formula)
LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]


def _ear_from_points(landmarks, indices, w, h):
    pts = [(landmarks[i].x * w, landmarks[i].y * h) for i in indices]
    p1, p2, p3, p4, p5, p6 = pts
    vertical = utils.euclidean(p2, p6) + utils.euclidean(p3, p5)
    horizontal = utils.euclidean(p1, p4)
    return vertical / (2.0 * horizontal) if horizontal else 0.0


class EyeTracker:
    """Tracks smoothed EAR for both eyes and exposes a single combined value."""

    def __init__(self, smoothing_frames: int = config.EAR_SMOOTHING_FRAMES):
        self._history = deque(maxlen=smoothing_frames)

    def update(self, landmarks, w, h) -> float:
        left = _ear_from_points(landmarks, LEFT_EYE, w, h)
        right = _ear_from_points(landmarks, RIGHT_EYE, w, h)
        avg = (left + right) / 2.0
        self._history.append(avg)
        return sum(self._history) / len(self._history)

    def reset(self):
        self._history.clear()

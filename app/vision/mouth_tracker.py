"""Mouth aspect ratio (MAR): lip gap over mouth width, smoothed."""

from collections import deque

from app import config, utils

MOUTH_LEFT = 61
MOUTH_RIGHT = 291
MOUTH_TOP = 13
MOUTH_BOTTOM = 14


class MouthTracker:
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

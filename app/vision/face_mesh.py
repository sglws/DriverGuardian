"""478 face landmarks per frame (MediaPipe Face Landmarker)."""

import os
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from app import config


class FaceMeshWrapper:
    def __init__(self, min_detection_confidence: float = 0.4,
                 min_tracking_confidence: float = 0.4):
        if not os.path.exists(config.FACE_LANDMARKER_MODEL_PATH):
            raise FileNotFoundError(
                f"Missing {config.FACE_LANDMARKER_MODEL_PATH}. Download it from "
                f"https://storage.googleapis.com/mediapipe-models/face_landmarker/"
                f"face_landmarker/float16/1/face_landmarker.task and place it in models/."
            )

        base_options = mp_python.BaseOptions(model_asset_path=config.FACE_LANDMARKER_MODEL_PATH)
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)
        self._last_ts_ms = -1

    def _next_timestamp_ms(self) -> int:
        ts = max(self._last_ts_ms + 1, int(time.monotonic() * 1000))
        self._last_ts_ms = ts
        return ts

    def process(self, rgb_frame):
        """The landmarks of one face, or None."""
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._landmarker.detect_for_video(mp_image, self._next_timestamp_ms())
        return result.face_landmarks[0] if result.face_landmarks else None

    def draw(self, frame, landmarks):
        h, w = frame.shape[:2]
        for lm in landmarks:
            cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 1, (0, 255, 0), -1)

    def close(self):
        self._landmarker.close()

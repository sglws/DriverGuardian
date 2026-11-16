"""Second opinion on driver presence (MediaPipe BlazeFace), used when the landmarker finds no face."""

import os
import time

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from app import config


class PresenceDetector:
    def __init__(self, min_detection_confidence: float = 0.4):
        if not os.path.exists(config.FACE_DETECTOR_MODEL_PATH):
            raise FileNotFoundError(
                f"Missing {config.FACE_DETECTOR_MODEL_PATH}. Download it from "
                f"https://storage.googleapis.com/mediapipe-models/face_detector/"
                f"blaze_face_short_range/float16/1/blaze_face_short_range.tflite "
                f"and place it in models/."
            )

        base_options = mp_python.BaseOptions(model_asset_path=config.FACE_DETECTOR_MODEL_PATH)
        options = mp_vision.FaceDetectorOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            min_detection_confidence=min_detection_confidence,
        )
        self._detector = mp_vision.FaceDetector.create_from_options(options)
        self._last_ts_ms = -1

    def _next_timestamp_ms(self) -> int:
        ts = max(self._last_ts_ms + 1, int(time.monotonic() * 1000))
        self._last_ts_ms = ts
        return ts

    def detect(self, rgb_frame):
        """True if a face is found."""
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._detector.detect_for_video(mp_image, self._next_timestamp_ms())
        return bool(result.detections)

    def close(self):
        self._detector.close()

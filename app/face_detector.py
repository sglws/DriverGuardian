"""
face_detector.py
-----------------
Phase 2 deliverable: driver presence detection.

Uses MediaPipe's Tasks API (mp.tasks.vision.FaceDetector), loading the
same short-range BlazeFace model the old mp.solutions.face_detection API
used under model_selection=0 - just accessed through a different wrapper,
since mediapipe 1.0.0 removed the legacy mp.solutions API entirely.

This stays a separate, lighter-weight detector from FaceMeshWrapper (not a
"do we have landmarks" check) so it can distinguish "driver absent" from
"camera blocked" independently of Face Mesh's stricter landmark requirements
(see risk_engine.py for how the two signals combine).
"""

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
        ts = max(self._last_ts_ms + 1, int(time.time() * 1000))
        self._last_ts_ms = ts
        return ts

    def detect(self, rgb_frame):
        """Returns True if any face/person presence is detected."""
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._detector.detect_for_video(mp_image, self._next_timestamp_ms())
        return bool(result.detections)

    def close(self):
        self._detector.close()

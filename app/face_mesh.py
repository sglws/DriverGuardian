"""
face_mesh.py
------------
Phase 3 deliverable: 468(+10 iris)-point facial landmark extraction.

Uses MediaPipe's Tasks API (mp.tasks.vision.FaceLandmarker) rather than the
legacy mp.solutions.face_mesh API, which mediapipe 1.0.0 removed entirely.
The underlying model and 478-point landmark topology/indices are unchanged
from the old API, so eye_tracker.py, head_pose.py, and utils.py's
landmark-index lookups all keep working without modification - only this
wrapper and the on-screen drawing (no built-in mesh-drawing helper in the
Tasks API) had to change.
"""

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
        # VIDEO mode requires strictly increasing timestamps per call.
        ts = max(self._last_ts_ms + 1, int(time.time() * 1000))
        self._last_ts_ms = ts
        return ts

    def process(self, rgb_frame):
        """Returns (landmarks, landmarks) or (None, None).

        Both tuple slots carry the same list for interface compatibility
        with the old (raw_list, drawable_object) signature - there's no
        separate "drawable" object in the Tasks API, draw() below just
        consumes the same landmark list directly.
        """
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._landmarker.detect_for_video(mp_image, self._next_timestamp_ms())
        if not result.face_landmarks:
            return None, None
        landmarks = result.face_landmarks[0]
        return landmarks, landmarks

    def draw(self, frame, face_landmarks_obj):
        """Simple dot overlay - the Tasks API has no built-in mesh/contour
        drawing helper like the old mp.solutions.drawing_utils did."""
        h, w = frame.shape[:2]
        for lm in face_landmarks_obj:
            cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 1, (0, 255, 0), -1)

    def close(self):
        self._landmarker.close()

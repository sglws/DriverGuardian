"""
face_detector.py
-----------------
Phase 2 deliverable: driver presence detection.

Uses MediaPipe's lightweight Face Detection model (NOT Face Mesh) as a
faster, more tolerant fallback signal for "is a person in frame at all",
independent of Face Mesh's stricter landmark requirements. Useful for
distinguishing "driver absent" from "camera blocked" (see face_mesh.py /
risk_engine.py for how the two signals are combined).
"""

import mediapipe as mp
from app import utils


class PresenceDetector:
    def __init__(self, min_detection_confidence: float = 0.4):
        self._mp_face_detection = mp.solutions.face_detection
        self._detector = self._mp_face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=min_detection_confidence,
        )
        self._mp_drawing = mp.solutions.drawing_utils

    def detect(self, rgb_frame):
        """Returns True if any face/person presence is detected."""
        results = self._detector.process(rgb_frame)
        return bool(results.detections)

    def close(self):
        self._detector.close()

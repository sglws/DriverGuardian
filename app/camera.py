"""
camera.py
---------
Phase 1 deliverable: verified live camera capture.
Thin wrapper around cv2.VideoCapture so main.py doesn't deal with raw OpenCV.
"""

import cv2
from app import config


class Camera:
    def __init__(self, index=config.CAMERA_INDEX,
                 width=config.FRAME_WIDTH, height=config.FRAME_HEIGHT):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Camera not found at index {index}. "
                f"Check connection or try a different index."
            )
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def read(self):
        """Returns (success, mirrored_bgr_frame)."""
        ret, frame = self.cap.read()
        if not ret:
            return False, None
        frame = cv2.flip(frame, 1)  # mirror for natural selfie-view
        return True, frame

    def release(self):
        self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

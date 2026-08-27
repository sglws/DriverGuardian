"""
camera.py
---------
Phase 1 deliverable: verified live camera capture.

Two backends, auto-selected:
- picamera2 (libcamera) - required for Raspberry Pi CSI ribbon-cable
  cameras (e.g. the imx219 family). OpenCV has no libcamera support at
  all (confirmed upstream: https://github.com/opencv/opencv/issues/22820),
  so on a Pi 5 - which dropped the legacy V4L2 camera stack entirely -
  cv2.VideoCapture(index) will open successfully but every read() fails.
- cv2.VideoCapture (V4L2) - USB webcams, and non-Pi dev machines where
  picamera2 isn't installed (it depends on system libcamera bindings that
  don't exist off-Pi, so it's never a pip dependency of this project).
"""

import sys

import cv2
from app import config

try:
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
except ImportError:
    _PICAMERA2_AVAILABLE = False


class Camera:
    def __init__(self, index=config.CAMERA_INDEX,
                 width=config.FRAME_WIDTH, height=config.FRAME_HEIGHT):
        self.using_picamera2 = _PICAMERA2_AVAILABLE

        if self.using_picamera2:
            self.picam2 = Picamera2()
            # NOTE: picamera2's "RGB888" format is a legacy/misleading name -
            # capture_array() actually returns BGR-ordered bytes for it,
            # which is exactly what OpenCV/this codebase expects. Do NOT
            # add a cv2.cvtColor(..., COLOR_RGB2BGR) here; that would
            # re-flip already-correct channels. See:
            # https://github.com/raspberrypi/picamera2/issues/260
            video_config = self.picam2.create_video_configuration(
                main={"size": (width, height), "format": "RGB888"}
            )
            self.picam2.configure(video_config)
            self.picam2.start()
            print(f"[camera] Using picamera2 (libcamera) at {width}x{height}")
        else:
            # No backend given, cv2.VideoCapture() defaults to whatever
            # OpenCV auto-picks - on Windows that's usually MSMF, which is
            # well known for slow/unbuffered read() (confirmed: 60-76ms per
            # frame here, ~45-50% of the entire frame budget - by far the
            # single biggest cost, well above MediaPipe or YOLO). DSHOW is
            # consistently faster for USB webcams on Windows; V4L2 is the
            # equivalent explicit choice on Linux/the Pi.
            backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_V4L2
            self.cap = cv2.VideoCapture(index, backend)
            if not self.cap.isOpened():
                raise RuntimeError(
                    f"Camera not found at index {index}. "
                    f"Check connection or try a different index."
                )
            # Request MJPEG instead of the default raw format: at 1280x720,
            # uncompressed YUYV over USB can exceed USB2.0 bandwidth and
            # forces the driver to silently throttle frame rate - MJPEG is
            # compressed on-camera, a fraction of the wire bandwidth. Must
            # be set before FRAME_WIDTH/HEIGHT - some backends renegotiate
            # format on a resolution change and would otherwise revert it.
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, config.TARGET_FPS_PREFERRED)
            # Default OS-level buffering can hand read() a stale queued
            # frame instead of the newest one, adding latency independent
            # of the format fix above - keep only the latest frame.
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print(f"[camera] Using cv2.VideoCapture ({'DSHOW' if backend == cv2.CAP_DSHOW else 'V4L2'}) "
                  f"at index {index}")
            # cap.set() returns a bool but doesn't guarantee the driver
            # actually applied it - some backends/cameras silently ignore
            # an unsupported FourCC/resolution/FPS combo and keep whatever
            # they were already doing. Read back what was actually
            # negotiated so a slow camera.read() can be diagnosed instead
            # of guessed at.
            actual_fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
            fourcc_str = "".join(chr((actual_fourcc >> (8 * i)) & 0xFF) for i in range(4))
            print(f"[camera] Actual negotiated settings: "
                  f"{int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
                  f"{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} "
                  f"fourcc={fourcc_str!r} fps={self.cap.get(cv2.CAP_PROP_FPS):.1f} "
                  f"buffersize={self.cap.get(cv2.CAP_PROP_BUFFERSIZE):.0f}")

    def read(self):
        """Returns (success, mirrored_bgr_frame)."""
        if self.using_picamera2:
            frame = self.picam2.capture_array()
            frame = cv2.flip(frame, 1)  # mirror for natural selfie-view
            return True, frame

        ret, frame = self.cap.read()
        if not ret:
            return False, None
        frame = cv2.flip(frame, 1)  # mirror for natural selfie-view
        return True, frame

    def release(self):
        if self.using_picamera2:
            self.picam2.stop()
        else:
            self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

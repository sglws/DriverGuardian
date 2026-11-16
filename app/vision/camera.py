"""Camera input: the Pi camera through picamera2, or a USB webcam through OpenCV.

Frames are mirrored, so the image moves like a mirror.
"""

import glob
import os
import sys

import cv2

from app import config

try:
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
except ImportError:
    _PICAMERA2_AVAILABLE = False

try:
    from libcamera import Transform
except ImportError:
    Transform = None


def _usb_camera_index():
    """First USB webcam's /dev/videoN on Linux, or None."""
    for dev in sorted(glob.glob("/sys/class/video4linux/video*"), key=lambda p: int(p.rsplit("video", 1)[1])):
        try:
            usb = "/usb" in os.path.realpath(os.path.join(dev, "device"))
            first = open(os.path.join(dev, "index")).read().strip() == "0"
        except OSError:
            continue
        if usb and first:
            return int(dev.rsplit("video", 1)[1])
    return None


class Camera:
    def __init__(self, index=config.CAMERA_INDEX,
                 width=config.FRAME_WIDTH, height=config.FRAME_HEIGHT):
        source = str(config.CAMERA_SOURCE).lower()
        if source not in ("auto", "csi", "usb"):
            raise RuntimeError(f"CAMERA_SOURCE must be auto, csi or usb, not {config.CAMERA_SOURCE!r}")
        if source == "csi" and not _PICAMERA2_AVAILABLE:
            raise RuntimeError("CAMERA_SOURCE = 'csi' needs picamera2 (Raspberry Pi OS: sudo apt install python3-picamera2)")
        self.using_picamera2 = _PICAMERA2_AVAILABLE and source != "usb"
        if source == "usb" and sys.platform.startswith("linux"):
            found = _usb_camera_index()
            if found is None:
                raise RuntimeError("CAMERA_SOURCE = 'usb' but no USB webcam was found (check the cable: ls /dev/video*)")
            index = found

        self._flip_in_software = True
        if self.using_picamera2:
            tuning, tuning_name = None, "default"
            if config.CAMERA_NOIR:
                try:
                    tuning_name = config.CAMERA_SENSOR + "_noir.json"
                    tuning = Picamera2.load_tuning_file(tuning_name)
                except (IndexError, KeyError, RuntimeError, OSError) as e:
                    print(f"[camera] NoIR tuning not available ({e}) - using the default")
                    tuning_name = "default"
            self.picam2 = Picamera2(tuning=tuning)   # libcamera reads the tuning only here
            extra = {}
            if Transform is not None:
                extra["transform"] = Transform(hflip=1)
                self._flip_in_software = False
            video_config = self.picam2.create_video_configuration(
                main={"size": (width, height), "format": "RGB888"},
                buffer_count=4,
                controls={"FrameRate": config.CAMERA_FPS,
                          **({"Saturation": 0.0} if config.CAMERA_GRAYSCALE else {})},
                **extra,
            )
            self.picam2.configure(video_config)
            self.picam2.start()
            print(f"[camera] Using picamera2 (libcamera) at {width}x{height}, "
                  f"{config.CAMERA_FPS} fps, mirror in {'software' if self._flip_in_software else 'hardware'}, "
                  f"tuning {tuning_name}{', grayscale' if config.CAMERA_GRAYSCALE else ''}")
        else:
            if sys.platform == "win32":
                backend = cv2.CAP_DSHOW
            elif sys.platform == "darwin":
                backend = cv2.CAP_AVFOUNDATION
            else:
                backend = cv2.CAP_V4L2
            self.cap = cv2.VideoCapture(index, backend)
            if not self.cap.isOpened():
                raise RuntimeError(
                    f"Camera not found at index {index}. "
                    f"Check connection or try a different index."
                )
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, config.TARGET_FPS_PREFERRED)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print(f"[camera] Using cv2.VideoCapture ({self.cap.getBackendName()}) "
                  f"at index {index}")
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
            if self._flip_in_software:
                frame = cv2.flip(frame, 1)
            return True, frame

        ret, frame = self.cap.read()
        if not ret:
            return False, None
        frame = cv2.flip(frame, 1)
        return True, frame

    def release(self):
        if self.using_picamera2:
            self.picam2.stop()
        else:
            self.cap.release()

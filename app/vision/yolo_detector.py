"""Object detection (phone, eating, drinking, smoking, seatbelt) with the trained YOLO model.

YoloProcess runs the model in its own process (yolo_service.py), so a slow
inference never stalls the video loop.
"""

import importlib.util
import os
import subprocess
import sys
import time
from collections import deque
from multiprocessing import Pipe

import cv2

from app import config, utils

_ULTRALYTICS_AVAILABLE = importlib.util.find_spec("ultralytics") is not None
_VOTED_KEYS = ("phone", "consumption", "cigarette")
EMPTY_STATE = {"phone": False, "consumption": False, "cigarette": False,
               "seatbelt_off": None, "raw_boxes": []}


def model_path():
    """The NCNN export (fastest on the Pi's CPU), else best.pt, else None."""
    if not _ULTRALYTICS_AVAILABLE:
        return None
    for path in (config.YOLO_NCNN_PATH, config.YOLO_MODEL_PATH):
        if os.path.exists(path):
            return path
    return None


class DetectionConfirmer:
    """Filters single-frame mistakes.

    Phone, eating/drinking and smoking count once seen in 2 of the last 3
    results. The model only knows a worn seatbelt, so "off" means the belt
    has not been seen for SEATBELT_OFF_CONFIRM_SEC (None until first seen).
    """

    def __init__(self, window=config.YOLO_CONFIRM_WINDOW, min_hits=config.YOLO_CONFIRM_MIN):
        self.min_hits = min_hits
        self._history = {key: deque(maxlen=window) for key in _VOTED_KEYS}
        self._seatbelt = utils.Hysteresis(confirm_in=config.SEATBELT_OFF_CONFIRM_SEC,
                                          confirm_out=config.SEATBELT_ON_CONFIRM_SEC)
        self._seatbelt_seen = False

    def update(self, raw: dict, now: float) -> dict:
        confirmed = dict(raw)
        for key in _VOTED_KEYS:
            hist = self._history[key]
            hist.append(bool(raw.get(key)))
            confirmed[key] = sum(hist) >= self.min_hits
        belt_seen = raw.get("seatbelt_off") is False
        self._seatbelt_seen = self._seatbelt_seen or belt_seen
        is_off = self._seatbelt.update(not belt_seen, now)
        confirmed["seatbelt_off"] = is_off if self._seatbelt_seen else None
        return confirmed


class YoloDetector:
    """Loads the model and turns one frame into detection flags."""

    def __init__(self):
        self.model = None
        path = model_path()
        if path is None:
            print("[yolo] no model or no 'ultralytics' - object detection disabled")
            return
        from ultralytics import YOLO
        import torch
        torch.set_num_threads(config.YOLO_INFERENCE_THREADS)
        try:
            import ncnn
            ncnn.set_omp_num_threads(config.YOLO_INFERENCE_THREADS)
        except ImportError:
            pass
        self.model = YOLO(path, task="detect")
        print(f"[yolo] loaded {path}")

    @property
    def available(self) -> bool:
        return self.model is not None

    def detect(self, bgr_frame, mouth_roi=None) -> dict:
        """Flags for one frame. mouth_roi = (cx, cy, radius) of the mouth, or None.

        raw_boxes holds every box as (x1, y1, x2, y2, label, conf, counted);
        counted means it passed its class threshold (and, for drinking, the
        mouth zone) and so fed the flags.
        """
        result = {**EMPTY_STATE, "raw_boxes": []}
        if not self.available:
            return result
        outputs = self.model.predict(bgr_frame, imgsz=config.YOLO_IMG_SIZE,
                                     conf=config.YOLO_CONF_THRESHOLD, verbose=False)
        if not outputs or outputs[0].boxes is None:
            return result

        def passes(category, conf):
            return conf >= config.YOLO_CLASS_CONF_THRESHOLDS.get(category, config.YOLO_CLASS_CONF_DEFAULT)

        def near_mouth(box):
            if mouth_roi is None:
                return True
            cx, cy, radius = mouth_roi
            return utils.box_near_point(box, cx, cy, radius * config.DRINK_MOUTH_RADIUS_MULT
                                        / config.MOUTH_PROXIMITY_RADIUS_MULT)

        for box in outputs[0].boxes:
            label = self.model.names.get(int(box.cls[0]), "?")
            conf = float(box.conf[0])
            xyxy = tuple(float(v) for v in box.xyxy[0])
            name = label.lower()
            counted = False
            if "belt" in name:          # checked first: "seatbelt" contains "eat"
                counted = passes("seatbelt", conf)
                if counted:
                    result["seatbelt_off"] = False
            elif "phone" in name:
                counted = passes("phone", conf)
                result["phone"] |= counted
            elif "drink" in name or "eat" in name:
                # Eating and drinking are one case; only drinking must be at the mouth.
                counted = passes("consumption", conf) and ("eat" in name or near_mouth(xyxy))
                result["consumption"] |= counted
            elif "smok" in name or "cigarette" in name:
                counted = passes("cigarette", conf)
                result["cigarette"] |= counted
            result["raw_boxes"].append((*xyxy, label, conf, counted))
        return result


class YoloProcess:
    """Runs YOLO in its own process (python -m app.vision.yolo_service).

    NCNN holds the GIL during inference, so a thread would still freeze the
    main loop. Only one frame is in flight at a time: submit() skips frames
    while the last one is still being processed, so the main loop never
    waits. A crashed process is restarted.
    """

    RESTART_COOLDOWN_SEC = 5.0

    def __init__(self):
        self.available = config.YOLO_ENABLED and model_path() is not None
        if not config.YOLO_ENABLED:
            print("[yolo] object detection disabled (YOLO_ENABLED = False)")
        self._latest = dict(EMPTY_STATE)
        self._conn = self._proc = None
        self._busy = False
        self._restart_at = 0.0
        self._last_result_at = None
        self._raw = None
        if self.available:
            self._start()

    def _start(self):
        parent, child = Pipe(duplex=True)
        try:
            self._proc = subprocess.Popen(
                [sys.executable, "-m", "app.vision.yolo_service", str(child.fileno())],
                pass_fds=(child.fileno(),), cwd=config.BASE_DIR, stdin=subprocess.DEVNULL)
        except Exception as e:
            print(f"[yolo] could not start the YOLO process: {e}")
            parent.close()
            self._restart_at = time.monotonic() + self.RESTART_COOLDOWN_SEC
            return
        finally:
            child.close()
        self._conn = parent
        self._busy = True   # until the process reports the model is loaded

    def _died(self):
        print(f"[yolo] YOLO process stopped - restarting in {self.RESTART_COOLDOWN_SEC:.0f} s")
        try:
            self._conn.close()
        except Exception:
            pass
        if self._proc is not None and self._proc.poll() is None:
            self._proc.kill()
        self._conn = self._proc = None
        self._busy = False
        self._restart_at = time.monotonic() + self.RESTART_COOLDOWN_SEC

    def _drain(self):
        if self._conn is None:
            if self.available and time.monotonic() >= self._restart_at:
                self._start()
            return
        try:
            while self._conn.poll():
                msg = self._conn.recv()
                kind = msg.get("type")
                if kind == "raw":
                    self._raw = msg["result"]
                elif kind != "ready":
                    self._latest = msg
                    self._last_result_at = time.monotonic()
                self._busy = False
        except (EOFError, OSError):
            self._died()

    def _send(self, payload) -> bool:
        self._drain()
        if self._conn is None or self._busy:
            return False
        try:
            self._conn.send(payload)
        except (OSError, EOFError):
            self._died()
            return False
        self._busy = True
        return True

    def submit(self, frame, mouth_roi) -> bool:
        """Send a frame if YOLO is idle (never blocks). The frame is shrunk to
        the model's input width first; no detail is lost."""
        h, w = frame.shape[:2]
        scale = min(1.0, config.YOLO_IMG_SIZE / w)
        if scale < 1.0:
            frame = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
        roi = tuple(v * scale for v in mouth_roi) if mouth_roi is not None else None
        return self._send((frame, roi, scale))

    def submit_raw(self, frame, mouth_roi) -> bool:
        """One detection without the confirmation filter (detection-delay test).
        The answer arrives through take_raw()."""
        self._raw = None
        return self._send(("raw", frame, mouth_roi))

    def take_raw(self):
        self._drain()
        raw, self._raw = self._raw, None
        return raw

    def get_latest(self) -> dict:
        self._drain()
        return self._latest

    def health(self, now: float) -> dict:
        if not self.available:
            state = "disabled"
        elif self._conn is None:
            state = "restarting"
        elif self._last_result_at is None:
            state = "starting"
        else:
            state = "running"
        age = now - self._last_result_at if self._last_result_at is not None else None
        return {"state": state, "result_age": age}

    def close(self):
        if self._conn is not None:
            try:
                self._conn.send(None)
                self._conn.close()
            except Exception:
                pass
        if self._proc is not None:
            try:
                self._proc.wait(timeout=2)
            except Exception:
                self._proc.kill()

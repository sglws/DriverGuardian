"""
yolo_detector.py
-----------------
Phase 8 deliverable: run pretrained YOLO Nano for a quick sanity check
(detects generic COCO classes like "cell phone", "bottle", "cup").

Phase 11: once `models/best.pt` exists, this module automatically prefers
it over the generic pretrained model - no code changes needed to switch.
Class-name matching (see detect() below) is substring-based and
case-insensitive, so it tolerates naming variation between datasets, e.g.
this project's current best.pt uses {Phone, Drinking, Eating, Smoking,
Seatbelt} rather than the datasets/data.yaml template's exact names.

Without a fine-tuned model, "seatbelt" and "cigarette" are NOT detectable
at all (not in COCO's 80 classes), so those come back as None (meaning
"unknown / not yet supported") rather than False.
"""

import os
import threading
import time
from collections import deque

from app import config, utils

try:
    from ultralytics import YOLO
    _ULTRALYTICS_AVAILABLE = True
except ImportError:
    _ULTRALYTICS_AVAILABLE = False

_VOTED_KEYS = ("phone", "drink", "food", "cigarette")


class DetectionConfirmer:
    """K-of-N voting across recent YOLO inferences: a flag only reads as
    active once it appears in at least `min_hits` of the last `window`
    inferences, and only clears once absence has the same weight of
    evidence. Symmetric by construction - cuts single-frame false positives
    from the COCO-proxy classes without masking a real, sustained detection.

    seatbelt_off is handled separately (see _update_seatbelt below): most
    fine-tuned models (including this project's current best.pt) only have
    a "Seatbelt" (worn/visible) class, not a distinct "unworn" one - there's
    no box to draw around an object that isn't there. "Off" has to be
    inferred from the belt going unseen for a sustained period instead of
    from a K-of-N vote on an explicit negative detection.

    That inference uses the same asymmetric Hysteresis pattern already used
    for presence/obstruction elsewhere in this app, deliberately lopsided:
    fast to confirm "on" (a real driving environment has the belt flicker
    out of view constantly - hand gestures, steering, camera angle - so a
    momentary re-detection should be trusted quickly), slow to confirm
    "off" (a real removal is sustained, not a single missed frame).
    """

    def __init__(self, window: int = config.YOLO_CONFIRM_WINDOW,
                 min_hits: int = config.YOLO_CONFIRM_MIN):
        self.window = window
        self.min_hits = min_hits
        self._history = {key: deque(maxlen=window) for key in _VOTED_KEYS}
        self._seatbelt_hysteresis = utils.Hysteresis(
            confirm_in=config.SEATBELT_OFF_CONFIRM_SEC,
            confirm_out=config.SEATBELT_ON_CONFIRM_SEC,
        )
        self._seatbelt_ever_seen = False

    def update(self, raw_state: dict, now: float) -> dict:
        confirmed = dict(raw_state)
        for key in _VOTED_KEYS:
            value = raw_state.get(key)
            if value is None:
                # Unsupported by current model - pass through untouched.
                continue
            hist = self._history[key]
            hist.append(bool(value))
            confirmed[key] = sum(hist) >= self.min_hits

        confirmed["seatbelt_off"] = self._update_seatbelt(raw_state.get("seatbelt_off"), now)
        return confirmed

    def _update_seatbelt(self, raw_value, now: float):
        if raw_value is not None:
            self._seatbelt_ever_seen = True
        # "off" condition this frame: anything except a confirmed sighting
        # of the belt worn (raw_value is False). Both "nothing detected"
        # (None) and an explicit negative class (True, if a future dataset
        # has one) count as "not currently seeing it worn".
        is_off = self._seatbelt_hysteresis.update(raw_value is not False, now)
        if not self._seatbelt_ever_seen:
            return None  # never confirmed visible yet - genuinely unknown
        return is_off


class YoloDetector:
    def __init__(self):
        self.model = None
        self.using_finetuned = False
        self.class_names = {}

        if not _ULTRALYTICS_AVAILABLE:
            print("[yolo_detector] 'ultralytics' not installed - object detection "
                  "(phone/drink/food/seatbelt) will be disabled. "
                  "Install with: pip install ultralytics")
            return

        weights_path = None
        if os.path.exists(config.YOLO_NCNN_PATH):
            # Same weights/classes as best.pt, just a faster CPU backend -
            # see config.YOLO_NCNN_PATH. ultralytics.YOLO() auto-detects the
            # NCNN directory format and returns the same Results/Boxes API
            # (.xyxy/.conf/.cls) as the .pt path below, so nothing else in
            # this file needs to branch on which backend is loaded.
            weights_path = config.YOLO_NCNN_PATH
            self.using_finetuned = True
        elif os.path.exists(config.YOLO_FINETUNED_PATH):
            weights_path = config.YOLO_FINETUNED_PATH
            self.using_finetuned = True
        elif os.path.exists(config.YOLO_PRETRAINED_PATH):
            weights_path = config.YOLO_PRETRAINED_PATH
        else:
            print(f"[yolo_detector] No weights found at "
                  f"{config.YOLO_PRETRAINED_PATH} or {config.YOLO_FINETUNED_PATH}. "
                  f"Download yolo11n.pt (see README) to enable detection.")
            return

        self.model = YOLO(weights_path)
        self.class_names = self.model.names  # {index: name}
        print(f"[yolo_detector] Loaded {'FINE-TUNED' if self.using_finetuned else 'PRETRAINED'} "
              f"model: {weights_path}")

    @property
    def available(self) -> bool:
        return self.model is not None

    def detect(self, bgr_frame, mouth_roi=None):
        """
        Runs inference on a single frame.

        `mouth_roi`, if given, is an (cx, cy, radius) tuple in pixel
        coordinates (see utils.mouth_roi). Per the flowchart's Case 5,
        eating/drinking/smoking only count when the object is near the
        mouth - a bottle in the cupholder or food on another seat shouldn't
        trigger a distraction warning. Phone/seatbelt are not mouth-gated
        (not mouth-specific per the spec). When `mouth_roi` is None (e.g. no
        face this frame), consumption classes fall back to ungated detection.

        Returns a dict:
          {
            "phone": bool,
            "drink": bool,
            "food": bool,
            "cigarette": bool | None,   # None if class unsupported by current model
            "seatbelt_off": bool | None,
            "raw_boxes": [(x1,y1,x2,y2,label,conf), ...]
          }
        """
        result = {
            "phone": False, "drink": False, "food": False,
            "cigarette": None, "seatbelt_off": None, "raw_boxes": [],
        }
        if not self.available:
            return result

        outputs = self.model.predict(
            bgr_frame, imgsz=config.YOLO_IMG_SIZE,
            conf=config.YOLO_CONF_THRESHOLD, verbose=False,
        )
        if not outputs:
            return result

        boxes = outputs[0].boxes
        if boxes is None:
            return result

        def near_mouth(box) -> bool:
            return mouth_roi is None or utils.box_near_point(box, *mouth_roi)

        def passes(category: str, conf: float) -> bool:
            # raw_boxes always gets every box regardless (diagnostic
            # visibility into what the model considered) - this only gates
            # whether a box counts toward the actual phone/drink/etc. flags.
            threshold = config.YOLO_CLASS_CONF_THRESHOLDS.get(category, config.YOLO_CLASS_CONF_DEFAULT)
            return conf >= threshold

        if self.using_finetuned:
            # Your custom class names from data.yaml (Phase 9-11), e.g.
            # ["phone", "seatbelt", "cigarette", "food", "drink"]
            for box in boxes:
                cls_idx = int(box.cls[0])
                label = self.class_names.get(cls_idx, str(cls_idx))
                conf = float(box.conf[0])
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
                result["raw_boxes"].append((x1, y1, x2, y2, label, conf))

                name = label.lower()
                if "phone" in name:
                    if passes("phone", conf):
                        result["phone"] = True
                elif "drink" in name or "bottle" in name or "cup" in name:
                    if passes("drink", conf):
                        result["drink"] = result["drink"] or near_mouth((x1, y1, x2, y2))
                elif "food" in name or "eating" in name:
                    if passes("food", conf):
                        result["food"] = result["food"] or near_mouth((x1, y1, x2, y2))
                elif "cigarette" in name or "smoking" in name:
                    if passes("cigarette", conf):
                        result["cigarette"] = bool(result["cigarette"]) or near_mouth((x1, y1, x2, y2))
                elif "seatbelt" in name or "belt" in name:
                    if not passes("seatbelt", conf):
                        continue
                    if "no" in name or "off" in name or "unworn" in name:
                        # Explicit negative class (some datasets have one) -
                        # trust it directly, this frame.
                        result["seatbelt_off"] = True
                    else:
                        # Plain "Seatbelt" = the belt IS visible/worn this
                        # frame. DetectionConfirmer infers "off" from
                        # SUSTAINED absence of this signal, not from here.
                        result["seatbelt_off"] = False
        else:
            # Fallback: approximate using generic COCO classes (Phase 8 sanity check)
            for box in boxes:
                cls_idx = int(box.cls[0])
                label = self.class_names.get(cls_idx, str(cls_idx))
                conf = float(box.conf[0])
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
                result["raw_boxes"].append((x1, y1, x2, y2, label, conf))

                if label in config.COCO_PHONE_CLASSES:
                    result["phone"] = True
                elif label in config.COCO_DRINK_CLASSES:
                    result["drink"] = result["drink"] or near_mouth((x1, y1, x2, y2))
                elif label in config.COCO_FOOD_CLASSES:
                    result["food"] = result["food"] or near_mouth((x1, y1, x2, y2))
                # cigarette / seatbelt stay None - not present in COCO

        return result


_EMPTY_YOLO_STATE = {
    "phone": False, "drink": False, "food": False,
    "cigarette": None, "seatbelt_off": None, "raw_boxes": [],
}


class YoloWorker:
    """Runs YoloDetector.detect() + DetectionConfirmer.update() entirely
    on its own background thread - same pattern as Esp32Link in
    alerts.py, for the same reason. YOLO inference is synchronous and,
    with a larger model (e.g. this project's current best.pt, a YOLO26-s
    checkpoint), can take on the order of a second or more per frame -
    running that directly in the main video loop freezes camera capture,
    MediaPipe, and display for the full duration of every inference. The
    main thread only ever calls submit() and get_latest() (both instant,
    thread-safe); it never waits on inference itself.
    """

    def __init__(self, yolo_detector: YoloDetector, confirmer: DetectionConfirmer):
        self._yolo = yolo_detector
        self._confirmer = confirmer
        self._lock = threading.Lock()
        self._pending = None  # (frame_copy, mouth_roi) or None
        self._latest_state = dict(_EMPTY_YOLO_STATE)
        self._stop = False
        self._new_frame = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def submit(self, frame, mouth_roi):
        """Called from the main video loop - instant, never blocks.
        Copies the frame (the caller keeps drawing on/reusing its own
        buffer right after this returns) and overwrites any not-yet-
        started previous submission, since only the latest frame matters."""
        with self._lock:
            self._pending = (frame.copy(), mouth_roi)
        self._new_frame.set()

    def get_latest(self) -> dict:
        """Called from the main video loop every frame - instant, returns
        whatever the most recently completed inference produced (the same
        cached-result pattern already used for the every-Nth-frame
        cadence, just now also covering however long inference itself
        takes)."""
        with self._lock:
            return self._latest_state

    def close(self):
        self._stop = True
        self._new_frame.set()

    def _worker(self):
        while not self._stop:
            self._new_frame.wait(timeout=1.0)
            self._new_frame.clear()
            if self._stop:
                break
            with self._lock:
                pending, self._pending = self._pending, None
            if pending is None:
                continue
            frame, mouth_roi = pending
            raw_state = self._yolo.detect(frame, mouth_roi=mouth_roi)
            confirmed = self._confirmer.update(raw_state, time.time())
            with self._lock:
                self._latest_state = confirmed

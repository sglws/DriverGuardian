"""
utils.py
--------
Small shared helper functions used across modules.
"""

import subprocess
import time
import cv2
import numpy as np

# vcgencmd get_throttled bit meanings (Raspberry Pi firmware) - low 4 bits
# are the CURRENT state, bits 16-19 are "has happened since boot" latches
# that stay set even after the condition clears, which matters here since
# the whole point is catching a brief throttling event between two FPS
# profiling windows that a snapshot alone would miss.
_THROTTLE_FLAGS = {
    0: "under-voltage NOW",
    1: "ARM frequency capped NOW",
    2: "currently throttled NOW",
    3: "soft temp limit active NOW",
    16: "under-voltage occurred since boot",
    17: "ARM frequency capping occurred since boot",
    18: "throttling occurred since boot",
    19: "soft temp limit occurred since boot",
}


def check_pi_thermal_status() -> dict:
    """Reads CPU temp + throttle state via vcgencmd (Raspberry Pi firmware
    tool). Sudden, intermittent FPS drops are a classic symptom of thermal
    throttling or under-voltage - no software fix elsewhere in this app can
    solve that, it needs a hardware fix (better PSU, heatsink/fan), so it's
    worth ruling in/out directly rather than guessing from software timing
    alone.

    Returns {"available": False} on anything but a real Pi (vcgencmd simply
    doesn't exist elsewhere - e.g. the Windows dev machine this was mostly
    profiled on this session, which is exactly why this was never actually
    checked until now).
    """
    try:
        temp_out = subprocess.run(
            ["vcgencmd", "measure_temp"], capture_output=True, timeout=2, text=True,
        )
        throttled_out = subprocess.run(
            ["vcgencmd", "get_throttled"], capture_output=True, timeout=2, text=True,
        )
    except Exception:
        return {"available": False}

    if temp_out.returncode != 0 or throttled_out.returncode != 0:
        return {"available": False}

    try:
        temp_c = float(temp_out.stdout.strip().split("=")[1].rstrip("'C\n"))
        throttled_bits = int(throttled_out.stdout.strip().split("=")[1], 16)
    except (IndexError, ValueError):
        return {"available": False}

    active_flags = [label for bit, label in _THROTTLE_FLAGS.items() if throttled_bits & (1 << bit)]
    return {
        "available": True,
        "temp_c": temp_c,
        "throttled_bits": throttled_bits,
        "flags": active_flags,
    }


def euclidean(p1, p2):
    """Euclidean distance between two (x, y) points."""
    return float(np.linalg.norm(np.array(p1) - np.array(p2)))


def timestamp() -> str:
    return time.strftime("%H:%M:%S")


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def frame_std_dev(gray_frame) -> float:
    """Grayscale standard deviation - near-zero means a near-uniform, out-of-
    focus image. Covers both a physically covered lens AND a hand/object
    held close to the camera (which produces the same low-texture blob)."""
    return float(np.std(gray_frame))


def frame_mean_brightness(gray_frame) -> float:
    """Mean grayscale brightness, used to decide when low-light enhancement
    is worth applying (a legitimately dark night cabin, not a covered lens)."""
    return float(np.mean(gray_frame))


def enhance_low_light(bgr_frame):
    """CLAHE contrast enhancement on the luma channel. Improves MediaPipe
    landmark/eye/head-pose accuracy at night on a plain RGB sensor, without
    the noise amplification of a naive brightness/gain boost."""
    lab = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


class Hysteresis:
    """Symmetric debounce: a boolean condition only flips the reported state
    after it has held steadily for a confirmation window - `confirm_in` to
    enter the "bad" state, `confirm_out` to leave it. This makes state
    transitions robust in both directions: a single bad frame can't cause a
    false escalation, and a single good frame can't prematurely clear an
    ongoing real condition.
    """

    def __init__(self, confirm_in: float, confirm_out: float, initial: bool = False):
        self.confirm_in = confirm_in
        self.confirm_out = confirm_out
        self.state = initial
        self._since = None  # timestamp the opposite-of-state condition started

    def update(self, condition: bool, now: float) -> bool:
        """`condition` is the raw, unsmoothed reading for this frame.
        Returns the debounced state."""
        target_delay = self.confirm_in if condition else self.confirm_out
        if condition != self.state:
            if self._since is None:
                self._since = now
            elif now - self._since >= target_delay:
                self.state = condition
                self._since = None
        else:
            self._since = None
        return self.state

    def reset(self, state: bool = False):
        self.state = state
        self._since = None


def mouth_roi(landmarks, w, h, radius_mult=3.5):
    """Returns (cx, cy, radius) in pixel coords for a circular region around
    the mouth, scaled up to cover an object (cup, food, cigarette) held near
    it - not just the lips themselves."""
    left = landmarks[61]
    right = landmarks[291]
    top = landmarks[13]
    bottom = landmarks[14]
    cx = (left.x + right.x + top.x + bottom.x) / 4.0 * w
    cy = (left.y + right.y + top.y + bottom.y) / 4.0 * h
    mouth_width = euclidean((left.x * w, left.y * h), (right.x * w, right.y * h))
    radius = max(mouth_width * radius_mult, 1.0)
    return cx, cy, radius


def box_near_point(box, cx, cy, radius) -> bool:
    """True if a YOLO box's center falls within `radius` of (cx, cy)."""
    x1, y1, x2, y2 = box[:4]
    bx, by = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    return euclidean((bx, by), (cx, cy)) <= radius


def seatbelt_label(seatbelt_off) -> str:
    """Human-facing label for the seatbelt_off tri-state - the raw
    "seatbelt_off=True/False" boolean reads like a double negative on the
    overlay (easy to misread as inverted at a glance)."""
    if seatbelt_off is None:
        return "UNKNOWN"
    return "OFF" if seatbelt_off else "ON"

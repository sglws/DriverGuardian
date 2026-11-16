"""Small shared helper functions used across modules."""

import glob
import os
import subprocess
import time

import cv2
import numpy as np

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


def _read_sysfs_thermal():
    """(temp_c, throttled_bits) from the kernel files, or None."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp_c = int(f.read().strip()) / 1000.0
        paths = glob.glob("/sys/devices/platform/soc*/soc*:firmware/get_throttled")
        if not paths:
            return None
        with open(paths[0]) as f:
            throttled_bits = int(f.read().strip(), 16)
        return temp_c, throttled_bits
    except (OSError, ValueError):
        return None


def check_pi_thermal_status() -> dict:
    """Pi CPU temperature and throttling flags (sysfs first, vcgencmd as a fallback)."""
    sysfs = _read_sysfs_thermal()
    if sysfs is not None:
        temp_c, throttled_bits = sysfs
    else:
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


def system_status():
    """Load, free RAM, swap and this process's memory and threads, from /proc. None off Linux."""
    try:
        with open("/proc/meminfo") as f:
            mem = {k: int(v.split()[0]) for k, v in
                   (line.split(":", 1) for line in f if ":" in line)}
        with open("/proc/self/status") as f:
            me = {k: v.strip() for k, v in (line.split(":", 1) for line in f if ":" in line)}
        load1 = os.getloadavg()[0]
    except (OSError, ValueError):
        return None
    return {
        "load1": load1,
        "cores": os.cpu_count(),
        "mem_available_mb": mem.get("MemAvailable", 0) / 1024,
        "swap_used_mb": (mem.get("SwapTotal", 0) - mem.get("SwapFree", 0)) / 1024,
        "rss_mb": int(me.get("VmRSS", "0 kB").split()[0]) / 1024,
        "threads": int(me.get("Threads", "0")),
    }


def euclidean(p1, p2):
    return float(np.linalg.norm(np.array(p1) - np.array(p2)))


def timestamp() -> str:
    return time.strftime("%H:%M:%S")


def frame_std_dev(gray_frame) -> float:
    """Near zero means a uniform image: the lens is covered."""
    return float(np.std(gray_frame))


def frame_mean_brightness(gray_frame) -> float:
    return float(np.mean(gray_frame))


def enhance_low_light(bgr_frame):
    """CLAHE contrast enhancement on the brightness channel."""
    ycrcb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2YCrCb)
    y, cr, cb = cv2.split(ycrcb)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    y = clahe.apply(y)
    return cv2.cvtColor(cv2.merge((y, cr, cb)), cv2.COLOR_YCrCb2BGR)


class Hysteresis:
    """Debounce: the state flips only after the condition has held for confirm_in
    (to turn on) or confirm_out (to turn off) seconds."""

    def __init__(self, confirm_in: float, confirm_out: float, initial: bool = False):
        self.confirm_in = confirm_in
        self.confirm_out = confirm_out
        self.state = initial
        self._since = None

    def update(self, condition: bool, now: float) -> bool:
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
    """(cx, cy, radius) in pixels: a circle around the mouth, radius_mult x the mouth width."""
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
    """True if the box centre is within radius of (cx, cy)."""
    x1, y1, x2, y2 = box[:4]
    bx, by = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    return euclidean((bx, by), (cx, cy)) <= radius


def seatbelt_label(seatbelt_off) -> str:
    if seatbelt_off is None:
        return "UNKNOWN"
    return "OFF" if seatbelt_off else "ON"

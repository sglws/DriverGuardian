"""Head pose from six landmarks (OpenCV solvePnP), and the looking-away and leaning timers.

Angles are measured against the driver's own calibrated pose.
"""

from collections import deque

import cv2
import numpy as np

from app import config, utils

POSE_LANDMARKS = {
    "nose_tip": 1, "chin": 152,
    "left_eye_corner": 263, "right_eye_corner": 33,
    "left_mouth_corner": 291, "right_mouth_corner": 61,
}

MODEL_POINTS_3D = np.array([   # generic 3D face, in mm, same order as POSE_LANDMARKS
    (0.0, 0.0, 0.0), (0.0, -63.6, -12.5),
    (-43.3, 32.7, -26.0), (43.3, 32.7, -26.0),
    (-28.9, -28.9, -24.1), (28.9, -28.9, -24.1),
], dtype=np.float64)


def estimate_pose(landmarks, w, h):
    """Returns (pitch, yaw, roll) in degrees, or (None, None, None) if solvePnP fails."""
    image_points = np.array([
        (landmarks[POSE_LANDMARKS[k]].x * w, landmarks[POSE_LANDMARKS[k]].y * h)
        for k in ["nose_tip", "chin", "left_eye_corner",
                  "right_eye_corner", "left_mouth_corner", "right_mouth_corner"]
    ], dtype=np.float64)

    focal_length = w   # no camera calibration: the usual approximation
    center = (w / 2, h / 2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1],
    ], dtype=np.float64)
    dist_coeffs = np.zeros((4, 1))

    success, rvec, tvec = cv2.solvePnP(
        MODEL_POINTS_3D, image_points, camera_matrix, dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not success:
        return None, None, None

    rot_mat, _ = cv2.Rodrigues(rvec)
    pose_mat = cv2.hconcat((rot_mat, tvec))
    _, _, _, _, _, _, euler = cv2.decomposeProjectionMatrix(pose_mat)
    pitch, yaw, roll = euler.flatten()
    if pitch > 90:
        pitch -= 180
    elif pitch < -90:
        pitch += 180
    return float(pitch), float(yaw), float(roll)


class HeadPoseTracker:
    def __init__(self):
        self.baseline_pitch = 0.0
        self.baseline_yaw = 0.0
        self.leaning_since = None
        self.turned_since = None
        self.recheck_at = None
        self.lean_case_active = False
        self._pitch_history = deque(maxlen=config.HEAD_POSE_SMOOTHING_FRAMES)
        self._yaw_history = deque(maxlen=config.HEAD_POSE_SMOOTHING_FRAMES)
        self._lean_confirm = utils.Hysteresis(config.LEAN_SCORE_CONFIRM_SEC, config.LEAN_SCORE_CONFIRM_SEC)

    def set_baseline(self, pitch: float, yaw: float):
        self.baseline_pitch = pitch
        self.baseline_yaw = yaw

    def smooth(self, pitch: float, yaw: float):
        self._pitch_history.append(pitch)
        self._yaw_history.append(yaw)
        return (sum(self._pitch_history) / len(self._pitch_history),
                sum(self._yaw_history) / len(self._yaw_history))

    def update(self, pitch: float, yaw: float, now: float, face_found: bool = True):
        if not face_found:
            self.leaning_since = None
            self.lean_case_active = False
            self.turned_since = None
            self.recheck_at = None
            return {
                "pitch_delta": 0.0,
                "yaw_delta": 0.0,
                "pitch_label": "FORWARD",
                "yaw_label": "CENTER",
                "is_leaning": False,
                "lean_confirmed": self._lean_confirm.update(False, now),
                "lean_elapsed": 0.0,
                "lean_case_active": False,
                "lean_recheck_due": False,
                "is_turned": False,
                "yaw_zone": "CENTER",
                "turn_elapsed": 0.0,
                "turn_risk": "NONE",
            }

        pitch, yaw = self.smooth(pitch, yaw)
        pitch_delta = pitch - self.baseline_pitch
        yaw_delta = yaw - self.baseline_yaw

        if pitch_delta > config.HEAD_LEAN_PITCH_DOWN_DELTA_DEG:
            pitch_label = "DOWN"
        elif pitch_delta < -config.HEAD_LEAN_PITCH_UP_DELTA_DEG:
            pitch_label = "UP/BACK"
        else:
            pitch_label = "FORWARD"

        abs_yaw = abs(yaw_delta)
        if abs_yaw > config.YAW_TURN_SEVERE_DELTA_DEG:
            yaw_zone = "SEVERE"
        elif abs_yaw > config.YAW_TURN_DELTA_DEG:
            yaw_zone = "MILD"
        else:
            yaw_zone = "CENTER"

        if yaw_delta < -config.YAW_TURN_DELTA_DEG:
            yaw_label = "LEFT"
        elif yaw_delta > config.YAW_TURN_DELTA_DEG:
            yaw_label = "RIGHT"
        else:
            yaw_label = "CENTER"

        # A turned head fakes pitch, so leaning only counts while facing roughly ahead.
        is_leaning = (pitch_label in ("DOWN", "UP/BACK")
                      and abs_yaw <= config.LEAN_IGNORE_WHEN_TURNED_DEG)
        lean_confirmed = self._lean_confirm.update(is_leaning, now)
        if is_leaning:
            if self.leaning_since is None:
                self.leaning_since = now
                self.lean_case_active = True
                self.recheck_at = now + config.HEAD_LEAN_RECHECK_DELAY_SEC
        else:
            self.leaning_since = None
            self.lean_case_active = False

        lean_elapsed = (now - self.leaning_since) if self.leaning_since is not None else 0.0

        is_turned = yaw_zone != "CENTER"
        if is_turned:
            if self.turned_since is None:
                self.turned_since = now
        else:
            self.turned_since = None

        turn_elapsed = (now - self.turned_since) if self.turned_since is not None else 0.0

        # LOW -> MEDIUM -> HIGH every HEAD_TURN_RECHECK_DELAY_SEC (a severe turn starts at MEDIUM).
        turn_risk = "NONE"
        if is_turned and turn_elapsed >= config.HEAD_TURN_SUSTAIN_SEC:
            escalations = int((turn_elapsed - config.HEAD_TURN_SUSTAIN_SEC) // config.HEAD_TURN_RECHECK_DELAY_SEC)
            if yaw_zone == "SEVERE":
                tiers = ["MEDIUM", "HIGH"]
            else:
                tiers = ["LOW", "MEDIUM", "HIGH"]
            turn_risk = tiers[min(escalations, len(tiers) - 1)]

        return {
            "pitch_delta": pitch_delta,
            "yaw_delta": yaw_delta,
            "pitch_label": pitch_label,
            "yaw_label": yaw_label,
            "is_leaning": is_leaning,
            "lean_confirmed": lean_confirmed,
            "lean_elapsed": lean_elapsed,
            "lean_case_active": self.lean_case_active,
            "lean_recheck_due": bool(self.recheck_at and now >= self.recheck_at),
            "is_turned": is_turned,
            "yaw_zone": yaw_zone,
            "turn_elapsed": turn_elapsed,
            "turn_risk": turn_risk,
        }

    def clear_lean_case(self):
        self.lean_case_active = False
        self.leaning_since = None
        self.recheck_at = None

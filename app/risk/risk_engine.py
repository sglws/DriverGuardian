"""Turns every signal into one risk level (SAFE, LOW, MEDIUM, HIGH) and one cause.

Three steps: the startup gate (WAITING until the seatbelt is on and the
breath test passed), immediate HIGH situations, then a score where each
condition adds points (1 = LOW, 2-3 = MEDIUM, 4+ = HIGH).
"""

from enum import Enum

from app import config
from app.risk.cabin_air import AirWatch, BreathTest
from app.vision.drowsiness import DrowsinessLevel


class Risk(Enum):
    WAITING = -1
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class PresenceState(Enum):
    DRIVER_PRESENT = 0
    DRIVER_ABSENT = 1
    CAMERA_BLOCKED = 2


class RiskEngine:
    def __init__(self):
        self._hits = {"phone": 0, "consumption": 0}
        self._prev = {"phone": False, "consumption": False}
        self.seatbelt_missing_since = None
        self.pre_drive_passed = not config.PRE_DRIVE_CHECK_ENABLED
        self.breath = BreathTest()
        self.air = AirWatch()

    def reset_pre_drive(self):
        """Re-arms the startup gate (new session or recalibration)."""
        self.pre_drive_passed = not config.PRE_DRIVE_CHECK_ENABLED
        self.breath.reset()

    def pop_events(self):
        """Breath-test results for the session log."""
        events, self.breath.events = self.breath.events, []
        return events

    def _repeated(self, key, active, trigger):
        """1 point while active; every trigger-th new occurrence adds 1 more. Returns (points, repeat)."""
        repeat = False
        if active and not self._prev[key]:
            self._hits[key] += 1
            if self._hits[key] >= trigger:
                self._hits[key], repeat = 0, True
        self._prev[key] = active
        return (1 + repeat if active else 0), repeat

    def evaluate(self, now, presence: PresenceState,
                 drowsiness_state: dict, head_pose_state: dict,
                 yolo_state: dict, seatbelt_supported: bool = True,
                 cabin: dict = None, uno_status: str = "disabled"):
        """Returns (Risk, messages, {"score", "case"})."""
        if not self.pre_drive_passed:
            if seatbelt_supported and yolo_state.get("seatbelt_off") is not False:
                return Risk.WAITING, ["Waiting for seatbelt"], {"case": "PRE_DRIVE"}
            waiting, alcohol_skipped = self.breath.update(now, cabin, uno_status)
            if waiting:
                case, message = waiting
                return Risk.WAITING, [message], {"case": case}
            self.pre_drive_passed = True
            skipped = [] if seatbelt_supported else ["SEATBELT CHECK SKIPPED - loaded model has no seatbelt class"]
            if alcohol_skipped:
                skipped.append(f"ALCOHOL CHECK SKIPPED - {alcohol_skipped}")
            print("[pre-drive] monitoring active" + (f" ({'; '.join(skipped)})" if skipped else ""))

        # Immediate HIGH, whatever the score.
        if presence == PresenceState.CAMERA_BLOCKED:
            return Risk.HIGH, ["Camera blocked - stopping vehicle"], {"case": "BLOCKED"}

        if presence == PresenceState.DRIVER_ABSENT:
            return Risk.HIGH, ["Driver not in seat - stopping vehicle"], {"case": "ABSENT"}

        if drowsiness_state["level"] == DrowsinessLevel.SLEEPING:
            return Risk.HIGH, ["Driver asleep - stopping vehicle"], {"case": "SLEEP"}

        if head_pose_state["lean_case_active"] and head_pose_state["lean_recheck_due"]:
            if head_pose_state["lean_confirmed"]:
                return Risk.HIGH, ["Prolonged head lean - stopping vehicle"], {"case": "LEAN_PROLONGED"}

        if head_pose_state["turn_risk"] == "HIGH":
            return Risk.HIGH, ["Prolonged look-away - stopping vehicle"], {"case": "TURN_PROLONGED"}

        # Score. case_candidates holds (priority, case): the lowest priority names the cause.
        score = 0
        messages = []
        case_candidates = []

        if drowsiness_state["level"] == DrowsinessLevel.DROWSY:
            score += 2
            messages.append("Eyes closing")
            case_candidates.append((1, "MICROSLEEP"))

        if head_pose_state["lean_confirmed"] and drowsiness_state["level"] != DrowsinessLevel.DROWSY:
            score += 2
            messages.append("Head leaning")
            case_candidates.append((2, "LEAN"))

        if head_pose_state["turn_risk"] == "MEDIUM":
            score += config.SCORE_MEDIUM_MIN
            messages.append(f'Looking away ({head_pose_state["yaw_label"].lower()}, prolonged)')
            case_candidates.append((3, "TURN"))
        elif head_pose_state["turn_risk"] == "LOW":
            score += config.SCORE_LOW_MIN
            messages.append(f'Looking away ({head_pose_state["yaw_label"].lower()})')
            case_candidates.append((3, "TURN"))

        if yolo_state.get("seatbelt_off") is True:
            if self.seatbelt_missing_since is None:
                self.seatbelt_missing_since = now
            elapsed = now - self.seatbelt_missing_since
            score += 2
            if elapsed >= config.SEATBELT_UNWORN_ESCALATE_SEC:
                messages.append(f"Seatbelt off > {config.SEATBELT_UNWORN_ESCALATE_SEC:.0f}s")
            else:
                messages.append("Seatbelt off")
            case_candidates.append((4, "SEATBELT"))
        else:
            self.seatbelt_missing_since = None

        points, repeat = self._repeated("phone", bool(yolo_state.get("phone")), config.PHONE_REPEAT_TRIGGER)
        if points:
            score += points
            messages.append("Repeated phone use" if repeat else "Phone in use")
            case_candidates.append((5, "PHONE_REPEAT" if repeat else "PHONE"))

        alcohol_air, smoke_air = self.air.update(now, cabin)
        if alcohol_air:
            score += config.SCORE_MEDIUM_MIN
            messages.append("Alcohol in the cabin (MQ-3)")
            case_candidates.append((4, "ALCOHOL_DRIVE"))

        smoke_camera = bool(yolo_state.get("cigarette"))
        if smoke_camera or smoke_air:
            score += config.SCORE_LOW_MIN
            messages.append("Smoking" if smoke_camera else "Smoke in the cabin (MQ-2)")
            case_candidates.append((6, "SMOKING"))

        points, repeat = self._repeated("consumption", bool(yolo_state.get("consumption")),
                                        config.CONSUMPTION_REPEAT_TRIGGER)
        if points:
            score += points
            messages.append("Repeated eating/drinking" if repeat else "Eating/drinking")
            case_candidates.append((7, "CONSUMPTION_REPEAT" if repeat else "CONSUMPTION"))

        if drowsiness_state["is_yawning"] or drowsiness_state["yawn_rate"] >= config.YAWN_RATE_DROWSY_THRESHOLD:
            score += config.SCORE_LOW_MIN
            messages.append("Yawning - signs of fatigue")
            case_candidates.append((8, "YAWN"))

        if score >= config.SCORE_HIGH_MIN:
            risk = Risk.HIGH
        elif score >= config.SCORE_MEDIUM_MIN:
            risk = Risk.MEDIUM
        elif score >= config.SCORE_LOW_MIN:
            risk = Risk.LOW
        else:
            risk = Risk.SAFE

        if not messages:
            messages = ["Continue driving"]

        case = min(case_candidates)[1] if case_candidates else "NONE"
        return risk, messages, {"score": score, "case": case}

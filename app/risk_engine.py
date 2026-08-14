"""
risk_engine.py
--------------
Phase 13 deliverable: fuse Face Mesh + YOLO signals into one risk level.

Design: a small point-scoring system rather than a flat if/elif chain.
This directly satisfies the spec's requirement that combined conditions
(e.g. drowsiness + phone use at the same time) should push the overall
risk HIGHER than either condition alone - a flat "take the max of each
individual case" approach can't represent that, but summed scores can.

A few conditions are still instant HIGH-risk overrides regardless of
score (sleeping at the wheel, camera physically blocked) because those
are unambiguous, single-cause emergencies that shouldn't be diluted by
scoring math.
"""

from enum import Enum

from app import config
from app.drowsiness import DrowsinessLevel


class Risk(Enum):
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
        self.phone_hits = 0
        self.consumption_hits = 0
        self.phone_prev_active = False
        self.consumption_prev_active = False
        self.seatbelt_missing_since = None

    def evaluate(self, now, presence: PresenceState,
                 drowsiness_state: dict, head_pose_state: dict,
                 yolo_state: dict):
        """
        Returns (Risk, list[str] action_messages, dict debug_info)
        """
        # ---- Instant HIGH overrides ----
        if presence == PresenceState.CAMERA_BLOCKED:
            return Risk.HIGH, ["Camera obstruction detected", "Hazard lights", "Autonomous stop"], {}

        if presence == PresenceState.DRIVER_ABSENT:
            return Risk.HIGH, ["Driver not detected in seat", "Hazard lights", "Autonomous stop"], {}

        if drowsiness_state["level"] == DrowsinessLevel.SLEEPING:
            return Risk.HIGH, [
                "Driver asleep detected", "Seat vibration ON", "Hazard lights ON",
                "ESP32 taking control", "Reduce speed gradually", "Stop vehicle",
            ], {}

        # ---- Head-lean sustained recheck (Case 2 escalation) ----
        # Uses the debounced lean_confirmed signal, not the raw per-frame
        # is_leaning, so a single noisy pitch reading can't fire this.
        if head_pose_state["lean_case_active"] and head_pose_state["lean_recheck_due"]:
            if head_pose_state["lean_confirmed"]:
                return Risk.HIGH, ["Prolonged head lean - behavior did not improve", "Autonomous stop"], {}

        # ---- Head-turn sustained escalation (Case 3, tiered) ----
        # turn_risk is a dedicated, dwell-time-gated state machine (see
        # head_pose.py) - not a flicker-prone boolean - so it's applied
        # directly rather than through the additive score below. HIGH is an
        # instant override (prolonged look-away is as unsafe as sleeping);
        # LOW/MEDIUM are applied as score floors further down so they can
        # still combine with other simultaneous risk factors.
        if head_pose_state["turn_risk"] == "HIGH":
            return Risk.HIGH, ["Prolonged head turn away from the road", "Autonomous stop"], {}

        # ---- Scored combination of lesser conditions ----
        score = 0
        messages = []

        if drowsiness_state["level"] == DrowsinessLevel.DROWSY:
            score += 2
            messages.append("Voice warning + Seat vibration + Reduce speed 50%")

        # Case 2 (head resting on hand / leaning): MEDIUM the moment leaning
        # is CONFIRMED (debounced - not a single noisy frame), independent of
        # the eye-closure signal above. The recheck block above escalates
        # this to HIGH if it's still unresolved 5s later.
        if head_pose_state["lean_confirmed"] and drowsiness_state["level"] != DrowsinessLevel.DROWSY:
            score += 2
            messages.append("Voice warning + Seat vibration + Reduce speed 50% (head leaning)")

        if head_pose_state["turn_risk"] == "MEDIUM":
            score += config.SCORE_MEDIUM_MIN
            messages.append(f'Audio: "Please focus on the road ahead." (head {head_pose_state["yaw_label"]} - prolonged)')
        elif head_pose_state["turn_risk"] == "LOW":
            score += config.SCORE_LOW_MIN
            messages.append(f'Audio: "Please focus on the road ahead." (head {head_pose_state["yaw_label"]})')

        phone_active = bool(yolo_state.get("phone"))
        if phone_active:
            score += 1
            if not self.phone_prev_active:
                self.phone_hits += 1
                if self.phone_hits >= config.PHONE_REPEAT_TRIGGER:
                    score += 1
                    messages.append("Repeated phone use -> Reduce speed 30% + Seat vibration + Hazard lights")
                    self.phone_hits = 0
                else:
                    messages.append('Audio: "Don\'t text and drive."')
            else:
                messages.append("Phone still in view")
        self.phone_prev_active = phone_active
        
        consumption_active = bool(yolo_state.get("drink") or yolo_state.get("food") or yolo_state.get("cigarette"))
        if consumption_active:
            score += 1
            if not self.consumption_prev_active:
                self.consumption_hits += 1
                if self.consumption_hits >= config.CONSUMPTION_REPEAT_TRIGGER:
                    score += 1
                    messages.append("Repeated eating/drinking/smoking -> elevated risk")
                    self.consumption_hits = 0
                else:
                    messages.append('Audio: "Please focus on driving."')
            else:
                messages.append("Consumption still in view")
        self.consumption_prev_active = consumption_active

        if yolo_state.get("seatbelt_off") is True:
            if self.seatbelt_missing_since is None:
                self.seatbelt_missing_since = now
            elapsed = now - self.seatbelt_missing_since
            score += 2
            if elapsed >= config.SEATBELT_UNWORN_ESCALATE_SEC:
                messages.append("Seatbelt unworn >10s -> Reduce speed 30%")
            else:
                messages.append("Audio warning + Seat vibration (seatbelt)")
        else:
            self.seatbelt_missing_since = None

        # ---- Map combined score to a risk tier ----
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

        return risk, messages, {"score": score}

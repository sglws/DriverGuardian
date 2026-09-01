"""
config.py
---------
Single source of truth for all tunable parameters and file paths.
Phase 1 deliverable: environment/config setup.
"""

import os

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

YOLO_PRETRAINED_PATH = os.path.join(MODELS_DIR, "yolo11n.pt")   # Phase 8 (COCO pretrained)
YOLO_FINETUNED_PATH = os.path.join(MODELS_DIR, "best.pt")        # Phase 11 (your custom classes)
# Phase 15: same weights as best.pt, exported to NCNN (training/export.py
# --format ncnn) for faster CPU inference on the Pi's ARM cores - identical
# classes/accuracy, just a different backend. Preferred automatically when
# present; falls back to best.pt untouched if this directory doesn't exist.
# Re-export whenever best.pt OR YOLO_IMG_SIZE changes (this dir doesn't
# auto-update, and a stale export crashes at inference time rather than
# just running slow - the .param/.bin shape has to match exactly).
YOLO_NCNN_PATH = os.path.join(MODELS_DIR, "best_ncnn_model")

# MediaPipe Tasks API models (Phases 2-3). Required since mediapipe 1.0.0
# removed the old bundled-model mp.solutions API - these are downloaded once
# from Google's official model bucket and committed to the repo (both are
# a few MB, same as yolo11n.pt).
FACE_LANDMARKER_MODEL_PATH = os.path.join(MODELS_DIR, "face_landmarker.task")
FACE_DETECTOR_MODEL_PATH = os.path.join(MODELS_DIR, "blaze_face_short_range.tflite")

# --------------------------------------------------------------------------
# Camera (Phase 1)
# --------------------------------------------------------------------------
CAMERA_INDEX = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
TARGET_FPS_MIN = 20     # non-functional requirement floor
TARGET_FPS_PREFERRED = 30

# --------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------
CALIBRATION_SEC = 3.0    # look straight ahead, eyes open, at startup

# --------------------------------------------------------------------------
# Eye / drowsiness thresholds (Phases 4-6)
# --------------------------------------------------------------------------
EAR_CLOSED_RATIO = 0.80          # eye considered closed if EAR < 80% of calibrated baseline
EAR_SMOOTHING_FRAMES = 3         # rolling average window, lower = faster response
EAR_MICROSLEEP_SEC = 1.0         # short closure - "microsleep" warning tier
EAR_SLEEPING_SEC = 2.5           # sustained closure - "sleeping" / HIGH risk tier

BLINK_WINDOW_SEC = 5.0
BLINK_RATE_DROWSY_THRESHOLD = 6  # blinks within window considered excessive/drowsy

# --------------------------------------------------------------------------
# Yawn detection (Mouth Aspect Ratio, same "relative to calibrated baseline"
# design as EAR above - a fixed absolute MAR doesn't generalize across
# different faces/cameras, but a multiple of the driver's own calibrated
# neutral/closed-mouth MAR does).
# --------------------------------------------------------------------------
MAR_SMOOTHING_FRAMES = 3
# A yawn is a much wider, more sustained gape than speech ever produces -
# an open vowel or a drawn-out word can still briefly cross a low ratio/
# short duration, which is what was causing normal talking to register as
# yawning. Both raised so only a genuine wide, held-open mouth counts:
MAR_YAWN_RATIO = 2.6            # mouth counted "open" once MAR exceeds this multiple of baseline
YAWN_MIN_DURATION_SEC = 3.2     # must stay open this long to count as a yawn, not talking/a word
YAWN_RATE_WINDOW_SEC = 10.0     # window for counting repeated yawns
YAWN_RATE_DROWSY_THRESHOLD = 2  # 2+ yawns within the window is itself a (still LOW-risk) signal

# --------------------------------------------------------------------------
# Head pose thresholds (Phase 7)
# --------------------------------------------------------------------------
# Split, not symmetric: a plain 6-point solvePnP pitch estimate is noisier
# tilting down than up (same underlying landmark foreshortening that makes
# EAR unreliable past EAR_SUPPRESS_PITCH_DOWN_DEG), and drivers legitimately
# glance down at the dashboard/phone mount/mirrors far more often than they
# tilt back - confirmed too sensitive specifically on forward/down lean in
# practice. Backward/up unchanged at the original value.
HEAD_LEAN_PITCH_DOWN_DELTA_DEG = 12.0  # forward lean (pitch_delta > this)
HEAD_LEAN_PITCH_UP_DELTA_DEG = 8.0     # backward lean (pitch_delta < -this)

# A quick mirror check (side/rearview) or a glance at the dash/AC controls is
# normal, SAFE driving behavior, not distraction - it's usually a moderate
# yaw excursion held for well under a second. Case 3 in the flowchart is
# specifically about looking away from the road for >=3s (talking to a
# passenger, staring out the side window, etc.), so both the angle and the
# sustain window are set wide enough to not fire on routine glances:
YAW_TURN_DELTA_DEG = 15.0         # "mild turn" zone entry - deviation from baseline yaw
# A real head turn to actually look at something (a passenger, a mirror, a
# blind spot) commonly reads 30-60 deg, not just a few degrees past 15 - with
# the old 35 deg severe cutoff, most genuine turns skipped straight past LOW
# into MEDIUM, so LOW almost never appeared. 50 deg reserves "severe" for a
# driver who is essentially no longer facing the windshield at all (fully
# turned to a passenger / out the side window), giving LOW its own solid
# 15-50 deg range that covers ordinary looking-away behavior.
YAW_TURN_SEVERE_DELTA_DEG = 50.0
HEAD_TURN_SUSTAIN_SEC = 3.0       # matches flowchart Case 3 ("turned >= 3 sec") exactly -
                                   # minimum dwell in a turned zone before ANY turn risk registers
HEAD_TURN_RECHECK_DELAY_SEC = 6.0 # further dwell time per escalation step (LOW->MEDIUM->HIGH,
                                   # or MEDIUM->HIGH for a severe-angle turn) - same cadence as
                                   # the head-lean recheck, for a single consistent state machine.
                                   # Gives LOW a full 3s-9s window of its own before escalating.

HEAD_LEAN_RECHECK_DELAY_SEC = 5.0 # re-check window for sustained leaning (Case 2 logic)
HEAD_POSE_SMOOTHING_FRAMES = 5    # rolling-average window for raw solvePnP pitch/yaw

# Minimum time the raw pitch signal must hold "leaning" before it's allowed
# to contribute risk score. Without this, a single noisy solvePnP frame
# (e.g. transient pitch/yaw coupling error while the driver is simply
# turning left/right) would inject a full Case-2 MEDIUM score for one frame
# and then drop it the next - visible as risk flickering between LOW and
# MEDIUM during an ordinary head turn.
LEAN_SCORE_CONFIRM_SEC = 0.5

# Beyond this pitch-down delta, the driver is looking down at the dashboard/
# phone rather than asleep - eyelid landmarks foreshorten and EAR becomes
# unreliable, so eye-closure escalation is suppressed in this band. Must be
# larger than HEAD_LEAN_PITCH_DOWN_DELTA_DEG so genuine leaning (Case 2)
# still gets caught independently.
EAR_SUPPRESS_PITCH_DOWN_DEG = 20.0

# --------------------------------------------------------------------------
# Presence / camera obstruction (Phase 2 + risk engine)
# --------------------------------------------------------------------------
NO_FACE_GRACE_SEC = 5.0            # no face detected for this long -> escalate (confirm-in)
PRESENCE_RECOVER_SEC = 0.5         # face reliably present for this long -> de-escalate (confirm-out)
FRAME_STD_BLOCKED_THRESHOLD = 3.0  # grayscale std-dev below this -> covered lens / hand / object
OBSTRUCTION_CONFIRM_SEC = 1.0      # low-variance must persist this long before flagging (confirm-in)
OBSTRUCTION_RECOVER_SEC = 0.5      # normal variance must persist this long to clear (confirm-out)

# --------------------------------------------------------------------------
# Low-light handling (plain RGB camera, must work day and night)
# --------------------------------------------------------------------------
LOW_LIGHT_BRIGHTNESS_THRESHOLD = 60.0  # mean grayscale brightness below this -> apply CLAHE enhancement

# --------------------------------------------------------------------------
# YOLO / distraction detection (Phases 8-12)
# --------------------------------------------------------------------------
# Kept low - this is the floor applied INSIDE model.predict() itself, so
# anything below it never even reaches our code at all. Per-class filtering
# happens afterward in yolo_detector.py via YOLO_CLASS_CONF_THRESHOLDS below,
# so this just needs to be <= the lowest per-class threshold to make sure
# nothing potentially useful gets discarded before that logic runs.
YOLO_CONF_THRESHOLD = 0.20

# Per-class confidence floor, applied in yolo_detector.py after the raw
# (low-threshold) predict() call above. A single global threshold can't
# serve every class well: phone needs to stay permissive (missed phones -
# false negatives - were the bigger problem), while consumption needs to
# be stricter (weak/wrong "Drinking"/"Eating" guesses - false positives -
# were the problem). Classes not listed fall back to YOLO_CLASS_CONF_DEFAULT.
YOLO_CLASS_CONF_THRESHOLDS = {
    "phone": 0.35,
    "consumption": 0.55,  # Drinking+Eating merged - see the merge note below
    "seatbelt": 0.35,     # already working well at this level - don't disturb
}
YOLO_CLASS_CONF_DEFAULT = 0.35
YOLO_IMG_SIZE = 640
YOLO_INFER_EVERY_N_FRAMES = 5     # run YOLO on 1-in-5 frames; reuse last result otherwise
PHONE_REPEAT_TRIGGER = 3          # Nth phone detection in session -> escalate
CONSUMPTION_REPEAT_TRIGGER = 3    # Nth eating/drinking/smoking detection -> escalate
SEATBELT_UNWORN_ESCALATE_SEC = 10.0

# Some fine-tuned models (e.g. this project's current best.pt) only have a
# "Seatbelt" (worn/visible) class, not a distinct "unworn" class - there's
# no box to draw around an absent object. seatbelt_off is inferred via
# Hysteresis (DetectionConfirmer in yolo_detector.py), deliberately
# asymmetric: a real cabin has the belt flicker out of view constantly
# (hands, steering, camera angle), so re-confirming "on" should be fast;
# a real removal is sustained, so confirming "off" should be patient.
SEATBELT_ON_CONFIRM_SEC = 0.5    # belt seen worn -> confirm "on" quickly
SEATBELT_OFF_CONFIRM_SEC = 6.0   # belt continuously unseen this long -> confirm "off"

# K-of-N voting: an object flag only counts as active once it appears in at
# least YOLO_CONFIRM_MIN of the last YOLO_CONFIRM_WINDOW inferences. Symmetric
# by construction - the same weight of evidence is needed to set or clear it.
YOLO_CONFIRM_WINDOW = 3
YOLO_CONFIRM_MIN = 2

# Case 5 (eating/drinking/smoking) requires the object to be near the mouth.
# Radius, as a multiple of the mouth-corner distance, defining "near".
# 3.5x worked out to roughly a quarter of the frame width in testing - far
# wider than "near the mouth" should mean, and a second, independent source
# of drink false positives alongside a too-low confidence threshold. 1.5x
# then turned out too tight the other way (a bottle genuinely being raised
# to drink wasn't counting) - nudged up modestly, not back toward 3.5.
MOUTH_PROXIMITY_RADIUS_MULT = 1.5

# COCO class names (pretrained yolo11n.pt) that approximate our target behaviors
# until the fine-tuned model (Phase 11) with real "phone/seatbelt/cigarette/food"
# classes is available.
COCO_PHONE_CLASSES = {"cell phone"}
# Drinking and Eating merged into one "consumption" signal - a single-frame
# object detector can't reliably tell the two apart (both are usually just
# "some small object near a hand near the mouth"; the fine-tuned model's own
# separate Drinking/Eating classes needed repeated confidence-threshold
# tuning for exactly this reason). risk_engine.py already ORs them into one
# consumption_active signal for scoring - this makes that unification
# consistent all the way down instead of just at the risk-scoring layer.
COCO_CONSUMPTION_CLASSES = {
    "bottle", "cup", "wine glass",
    "banana", "apple", "sandwich", "orange", "pizza", "donut", "cake",
}
# NOTE: "seatbelt" and "cigarette" do NOT exist in COCO's 80 classes.
# These will read as None (unknown) until Phase 9-12 (your fine-tuned best.pt) is trained.

# --------------------------------------------------------------------------
# Risk engine scoring (Phase 13)
# --------------------------------------------------------------------------
# Score thresholds -> Risk level (used for *combined* conditions, e.g.
# drowsy + phone use together should be worse than either alone).
SCORE_LOW_MIN = 1
SCORE_MEDIUM_MIN = 2
SCORE_HIGH_MIN = 4

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
CONSOLE_LOG_INTERVAL_SEC = 0.5
CSV_LOG_INTERVAL_SEC = 1.0
PROFILE_LOG_INTERVAL_SEC = 5.0  # per-stage timing breakdown, to find the real FPS bottleneck

# --------------------------------------------------------------------------
# ESP32 link (Phase 14 - Bluetooth SPP / RFCOMM)
# --------------------------------------------------------------------------
# Connects with a raw AF_BLUETOOTH/BTPROTO_RFCOMM socket directly to the
# ESP32's MAC address - no `rfcomm bind`/`/dev/rfcommX` device file
# involved. Requires the device to already be paired + trusted first
# (`bluetoothctl pair`/`trust` - see README); that part is unchanged.
# Fill in your ESP32's actual MAC address (`bluetoothctl devices` after
# pairing, or read it off the ESP32's own Serial Monitor output at boot).
ESP32_MAC_ADDRESS = "08:B6:1F:3B:1A:AA"
ESP32_RFCOMM_PORT = 1  # SPP channel - matches BluetoothSerial's default on the ESP32 side
ESP32_SEND_INTERVAL_SEC = 0.3   # also the de facto link heartbeat - see esp32/ sketch
# HIGH risk re-speaks its warning continuously (not just on change, unlike
# LOW/MEDIUM) as a deliberate sustained audible alarm. _speak() now runs
# on its own thread rather than blocking the video loop, but firing a new
# one every single frame would still be wasteful (and pyttsx3 isn't meant
# to be driven by overlapping calls) - rate-limited to this cadence
# instead, still a repeating alarm, just not one fired every frame.
HIGH_RISK_VOICE_REPEAT_SEC = 3.0
# Temporary kill switch for isolating TTS's CPU cost from FPS measurements
# - even non-blocking, the speech thread still does real audio synthesis
# work concurrently with the main thread while an utterance plays, which
# can still cost FPS through CPU contention rather than a hard block.
# Flip back to True once done profiling; [VOICE] text still prints either
# way so alerts stay visible in the console/log.
VOICE_ALERTS_ENABLED = False
ESP32_RECONNECT_COOLDOWN_SEC = 5.0  # don't hammer a failed connection attempt every frame
ESP32_SEND_FAILURE_TOLERANCE = 3    # consecutive send failures before tearing down + reconnecting
                                     # (a single slow send is often just a transient hiccup, not a
                                     # real disconnect - see Esp32Link.send() in alerts.py)

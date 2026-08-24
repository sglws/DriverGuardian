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
HEAD_LEAN_PITCH_DELTA_DEG = 8.0   # deviation from baseline pitch, either direction

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
# larger than HEAD_LEAN_PITCH_DELTA_DEG so genuine leaning (Case 2) still
# gets caught independently.
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
# TEMPORARILY lowered from 0.45 to help diagnose "seatbelt/smoking not
# detecting at all" - this is applied INSIDE model.predict(), so anything
# below it never even reaches our code. Lowering it surfaces weak/borderline
# boxes in the new raw-detection overlay/console output so we can tell
# whether the model is trying and just under-confident (raise this back
# toward 0.4-0.45 once you see real numbers) vs. never proposing a box for
# that class at all (a training-data problem, not a threshold one).
YOLO_CONF_THRESHOLD = 0.20
YOLO_IMG_SIZE = 640
YOLO_INFER_EVERY_N_FRAMES = 3     # run YOLO on 1-in-3 frames; reuse last result otherwise
PHONE_REPEAT_TRIGGER = 3          # Nth phone detection in session -> escalate
CONSUMPTION_REPEAT_TRIGGER = 3    # Nth eating/drinking/smoking detection -> escalate
SEATBELT_UNWORN_ESCALATE_SEC = 10.0

# Some fine-tuned models (e.g. this project's current best.pt) only have a
# "Seatbelt" (worn/visible) class, not a distinct "unworn" class - there's
# no box to draw around an absent object. seatbelt_off is inferred from the
# belt going UNSEEN for this long, not from an explicit negative detection.
# See DetectionConfirmer in yolo_detector.py.
SEATBELT_ABSENCE_INFER_SEC = 8.0

# K-of-N voting: an object flag only counts as active once it appears in at
# least YOLO_CONFIRM_MIN of the last YOLO_CONFIRM_WINDOW inferences. Symmetric
# by construction - the same weight of evidence is needed to set or clear it.
YOLO_CONFIRM_WINDOW = 3
YOLO_CONFIRM_MIN = 2

# Case 5 (eating/drinking/smoking) requires the object to be near the mouth.
# Radius, as a multiple of the mouth-corner distance, defining "near".
MOUTH_PROXIMITY_RADIUS_MULT = 3.5

# COCO class names (pretrained yolo11n.pt) that approximate our target behaviors
# until the fine-tuned model (Phase 11) with real "phone/seatbelt/cigarette/food"
# classes is available.
COCO_PHONE_CLASSES = {"cell phone"}
COCO_DRINK_CLASSES = {"bottle", "cup", "wine glass"}
COCO_FOOD_CLASSES = {"banana", "apple", "sandwich", "orange", "pizza", "donut", "cake"}
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
ESP32_RECONNECT_COOLDOWN_SEC = 5.0  # don't hammer a failed connection attempt every frame
ESP32_SEND_FAILURE_TOLERANCE = 3    # consecutive send failures before tearing down + reconnecting
                                     # (a single slow send is often just a transient hiccup, not a
                                     # real disconnect - see Esp32Link.send() in alerts.py)

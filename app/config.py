"""
config.py
---------
Single source of truth for all tunable parameters and file paths.
Phase 1 deliverable: environment/config setup.
"""

import os
import sys

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

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
TARGET_FPS_PREFERRED = 30   # USB webcams (they usually only offer 15/30)
# Pi camera (picamera2) frame rate. The app is a 12+ Hz monitor; frames the
# pipeline can't use were still captured and run through the ISP. 20 keeps
# headroom above the requirement and leaves the rest of the CPU idle -
# cooler Pi, smoother desktop. Raise it if the Pi has clear CPU headroom.
CAMERA_FPS = 20

# When False: skips all drawing (face mesh dots, YOLO boxes, text panel)
# and the cv2.imshow()/waitKey() window entirely - camera, MediaPipe,
# YOLO, risk logic, and console/CSV logging all still run normally.
# Originally scoped as a production/no-preview-needed deployment option;
# currently doubling as a diagnostic toggle to isolate whether a reported
# system-wide freeze (CPU and RAM both already ruled out) is coming from
# the camera/ISP path or from cv2.imshow()/compositor rendering - if the
# freeze still happens with this False, it's not about the display.
# No 'r' recalibration key when False (see main.py); quit via Ctrl+C.
# Local preview window: ON on a Mac/PC, OFF on the Pi (Linux). On the Pi,
# watch the app in a browser instead (WEB_VIEW below) - over remote desktop
# (Pi Connect / VNC) the constantly-changing camera window makes the whole
# remote desktop lag, since the Pi 5 re-encodes its screen in software.
# Override for one run: DG_DISPLAY=1 (e.g. a monitor plugged into the Pi)
# or DG_DISPLAY=0.
DISPLAY_ENABLED = not sys.platform.startswith("linux")
# ---- Live view in a web browser (app/web_view.py) ----
# Open http://<pi-hostname>.local:8080 on any device on the same network
# (e.g. http://pi5.local:8080). Frames are only encoded while someone is
# watching, so it costs nothing otherwise.
WEB_VIEW_ENABLED = True
WEB_VIEW_HOST = "0.0.0.0"       # all network interfaces; "127.0.0.1" = this machine only
WEB_VIEW_PORT = 8080
WEB_VIEW_FPS = 10               # stream frame rate (detection still runs at full rate)
WEB_VIEW_WIDTH = 1280           # stream width in pixels; 1280 = full camera resolution
WEB_VIEW_JPEG_QUALITY = 80      # ~5 Mbit/s at 1280 px / 10 fps; lower both for a weak network

# CPU priority for the whole app (0 = normal, 19 = lowest). See main.py:
# keeps the desktop, audio and Bluetooth responsive under full load.
APP_NICE = 10
# How many processed frames per actual cv2.imshow() call - 1 means every
# frame (default, no behavior change). This app's Qt build has no OpenGL
# support (confirmed via cv2.getBuildInformation()), so every displayed
# frame is a full 1280x720 software-rendered push into the compositor -
# forcing XWayland instead of native Wayland didn't fix a reported freeze,
# which (combined with cv2.imshow() itself always timing fast in
# [PROFILE] - "display" stage - even during a freeze) points at the
# compositor's own async rendering of what gets handed to it, not the
# handoff itself. Showing fewer, not smaller, frames tests whether cutting
# that sustained software-rendering load reduces how often it happens.
# cv2.waitKey() still runs every frame regardless (see main.py) - it
# processes GUI/keyboard events for the window, unrelated to whether a
# new frame was actually pushed that iteration.
# 1 = the preview updates on every processed frame. 2 (half rate) was tried
# to lighten the compositor load but made the desktop feel worse on the Pi,
# not better - left at 1. Try DG_DISPLAY_EVERY=2 for a one-off comparison.
DISPLAY_EVERY_N_FRAMES = 1
# Scale factor applied to the preview frame just before cv2.imshow() -
# 1.0 means no resize. Detection is completely unaffected: everything
# (MediaPipe, YOLO, risk logic) already ran on the full-resolution frame
# by this point, so this only shrinks what the GUI has to paint.
#
# Background: per-frame timing showed imshow() is ~1ms while cv2.waitKey()
# runs ~24ms normally and spikes past 100ms during a visible stutter -
# OpenCV's Qt backend only *queues* the repaint in imshow(), so the actual
# software blit happens inside the event loop (i.e. inside waitKey()), and
# this Qt build has no OpenGL support (cv2.getBuildInformation()).
#
# Measured results differ sharply by machine, so this stays 1.0 by default:
#   - Windows laptop (cv2.VideoCapture/DSHOW): 0.5 cut waitKey 24.5ms ->
#     2.2ms. Blit cost there really is proportional to pixel count.
#   - Raspberry Pi (Wayland compositor): 0.5 changed nothing at all -
#     waitKey stayed at 24.4ms with the same ~106ms spikes. So the Pi's
#     waitKey cost is NOT pixel-count-bound; it looks more like blocking
#     on compositor frame callbacks (a vsync-style wait), which no amount
#     of shrinking the frame can avoid.
DISPLAY_SCALE = 1.0

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
# tilt back, so down stays the less twitchy of the two. It was pushed to 15
# while down-lean was firing on its own, but most of that turned out to be
# phantom pitch from head turns, which LEAN_IGNORE_WHEN_TURNED_DEG below now
# suppresses at the source - 15 was then high enough that real forward leans
# stopped registering at all, so it comes back down to just above the up
# value rather than compensating twice for the same noise.
HEAD_LEAN_PITCH_DOWN_DELTA_DEG = 12.0  # forward lean (pitch_delta > this)
HEAD_LEAN_PITCH_UP_DELTA_DEG = 11.0    # backward lean (pitch_delta < -this)
# Lean is ignored once the head is turned more than this far from straight
# ahead. Pitch comes from a 6-landmark solvePnP fit, and on a real turn the
# far-side eye/mouth corners go partly out of view and drift, skewing pitch
# (measured: ~8 deg of false pitch at a 40 deg turn) - on top of the genuine
# downward tilt that checking a door mirror or blind spot involves. Together
# those pushed ordinary head turns past the lean threshold. Past this angle
# the turn logic (YAW_TURN_* below) owns the behaviour instead, so it's
# tracked as a turn rather than double-counted as a lean.
LEAN_IGNORE_WHEN_TURNED_DEG = 20.0

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
# Pre-drive readiness check (startup gate)
# --------------------------------------------------------------------------
# One condition gates the start of monitoring: the seatbelt is confirmed
# fastened. Driver presence isn't part of it - calibration runs immediately
# before and cannot finish without a face, so the driver is already known to
# be seated.
#
# While the belt is still off the system stays deliberately quiet: it reports
# the WAITING state, which triggers no voice and no ESP32 actuators. WAITING
# is still sent on the normal ESP32 interval rather than going silent - the
# ESP32 treats 6 s of silence (BT_TIMEOUT_MS) as a lost link and raises the full HIGH alarm.
# Getting in and buckling up is normal behaviour, not a fault to alarm about.
# The moment the belt is confirmed, normal monitoring begins.
#
# "Confirmed" means seen, not merely un-contradicted: seatbelt_off is a
# tri-state and sits at None until the belt has actually been detected once
# (see yolo_detector._update_seatbelt), so an unverified belt can't pass the
# gate by default. The check only applies while the fine-tuned model is
# loaded - the COCO-pretrained fallback has no seatbelt class at all, so
# enforcing it there would leave the app permanently waiting with nothing the
# driver could do about it.
#
# Latched once passed: from that point the normal driving rules
# (SEATBELT_UNWORN_ESCALATE_SEC, presence handling, etc.) own the behaviour,
# so unbuckling later is a seatbelt violation rather than a failed startup.
# Pressing 'r' to recalibrate re-arms it, since that restarts the session.
PRE_DRIVE_CHECK_ENABLED = True

# --------------------------------------------------------------------------
# Presence / camera obstruction (Phase 2 + risk engine)
# --------------------------------------------------------------------------
# Leaving the seat or covering the camera must change the state within 1 s.
# Trade-off: a head turn far enough that no face is found at all (a long
# over-the-shoulder look) also counts as "not detected" after 1 s.
NO_FACE_GRACE_SEC = 0.9            # no face detected for this long -> escalate (confirm-in)
PRESENCE_RECOVER_SEC = 0.5         # face reliably present for this long -> de-escalate (confirm-out)
FRAME_STD_BLOCKED_THRESHOLD = 3.0  # grayscale std-dev below this -> covered lens / hand / object
# Shorter than NO_FACE_GRACE_SEC so a covered lens is reported as "camera
# blocked" (the specific cause) rather than first as "driver not detected".
OBSTRUCTION_CONFIRM_SEC = 0.5      # low-variance must persist this long before flagging (confirm-in)
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
YOLO_ENABLED = True   # False = no object detection at all (diagnostics only)
YOLO_CONF_THRESHOLD = 0.20

# Per-class confidence floor, applied in yolo_detector.py after the raw
# (low-threshold) predict() call above. A single global threshold can't
# serve every class well: phone needs to stay permissive (missed phones -
# false negatives - were the bigger problem), while consumption needs to
# be stricter (weak/wrong "Drinking"/"Eating" guesses - false positives -
# were the problem). Classes not listed fall back to YOLO_CLASS_CONF_DEFAULT.
YOLO_CLASS_CONF_THRESHOLDS = {
    "phone": 0.25,
    "consumption": 0.55,  # Drinking+Eating merged - see the merge note below
    "seatbelt": 0.23,     # already working well at this level - don't disturb
    "cigarette": 0.35,    # same as seatbelt - don't disturb
}
YOLO_CLASS_CONF_DEFAULT = 0.35
YOLO_IMG_SIZE = 640
# The camera frame is 16:9, but the square 640x640 model pads it with ~44%
# grey bars that YOLO still has to process. The 384x640 export (same
# weights, same detail - 640 px wide either way) does ~40% less work per
# inference (measured 22.0 -> 13.1 ms). Off until checked on the Pi: run
# once with each and compare the boxes/confidences on the overlay.
# Re-create it with: python training/export.py --format ncnn --imgsz 384 640
YOLO_USE_16X9_MODEL = False
if YOLO_USE_16X9_MODEL:
    YOLO_NCNN_PATH = os.path.join(MODELS_DIR, "best_384x640_ncnn_model")
    YOLO_IMG_SIZE = (384, 640)   # (height, width)
# How often a frame is handed to YOLO (it runs in its own process - see
# yolo_detector.YoloProcess). Time-based, so YOLO's CPU load no longer
# grows when the main loop gets faster. 0.4 s ~ the old every-6th-frame
# cadence at 15 FPS; with 2-of-3 confirmation a detection is confirmed in
# roughly 0.8-1.0 s (the 1 s detection-delay requirement).
YOLO_INTERVAL_SEC = 0.4
# Uncapped, NCNN/torch grab every CPU core for the duration of each
# inference call. On the Pi that starves the desktop session itself -
# window manager, compositor, mouse cursor - of CPU time each time YOLO
# runs, not just this app (confirmed: "whole system freezes, even moving
# the mouse" while running with a live desktop session). Leaving only 1
# core free (cpu_count - 1) still left visible compositor stalls - checked
# mediapipe 0.10.14's BaseOptions directly (no num_threads exposed in this
# version's Python API, only a CPU/GPU delegate choice), so MediaPipe's own
# per-frame thread usage can't be capped the same way; leaving 2 cores free
# instead gives the compositor more room to coexist with whatever MediaPipe
# is doing on its own, uncapped, every single frame.
YOLO_INFERENCE_THREADS = max(1, os.cpu_count() - 2)
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
SEATBELT_OFF_CONFIRM_SEC = 12.0  # belt continuously unseen this long -> confirm "off".
                                 # Raised from 6.0: this only ever applies AFTER the belt
                                 # has been confirmed worn at least once (see
                                 # _seatbelt_ever_seen in yolo_detector.py), so a belt that
                                 # drops out of view is far more likely occluded - hands,
                                 # steering, arm across the chest, camera angle - than
                                 # actually unbuckled mid-drive. Being patient here costs
                                 # little because a genuine removal stays unseen and still
                                 # trips, just later.

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
# The per-second status line in the terminal. False = no live log (the CSV
# session log, [PROFILE]/[SYSTEM] diagnostics and warnings still print).
CONSOLE_LOG_ENABLED = True
CONSOLE_LOG_INTERVAL_SEC = 1.0
CSV_LOG_INTERVAL_SEC = 1.0
# Requirement check: "classification update rate of at least 0.2 Hz" means
# no gap between two consecutive risk classifications may exceed 5 s.
# main.py prints a [RISK-RATE] line on the [PROFILE] cadence with the rate
# and the LONGEST gap (the worst case is what the requirement is about - an
# average of 15 Hz still fails if one frame stalls for 6 s).
RISK_UPDATE_MIN_HZ = 0.2
# When True, every single classification's monotonic timestamp is written
# to logs/risk_updates_<session>.csv for offline verification with
# tools/check_update_rate.py. Off by default: one row per frame is ~15
# rows/s, harmless but unnecessary outside a test run.
RISK_UPDATE_LOG = False
PROFILE_LOG_INTERVAL_SEC = 5.0  # per-stage timing breakdown, to find the real FPS bottleneck
# Per-frame outlier detection (see main.py's [STUTTER] line). [PROFILE]
# averages over 5s, which hides which *individual* frame stalled - the gap
# that made a reported visible stutter hard to pin down even after YOLO's
# own average dropped to ~0ms. A frame taking STUTTER_MULTIPLIER x the
# rolling average of the last STUTTER_WINDOW_FRAMES gets logged with its
# own per-stage breakdown, so the culprit stage is visible directly
# instead of inferred by testing one candidate at a time.
STUTTER_WINDOW_FRAMES = 30
STUTTER_MIN_SAMPLES = 10   # don't flag anything until the baseline is meaningful
STUTTER_MULTIPLIER = 2.0   # flag frames at least this many times the rolling average

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
# Kill switch for dev machines without the real ESP32 nearby (e.g. a
# laptop). Esp32Link is deliberately synchronous (see its docstring - a
# background thread here caused a proven, severe freeze on the Pi), which
# means a reconnect attempt blocks the main loop for however long
# connect() takes to fail when unreachable - confirmed on Windows, that's
# multiple real seconds (WinError 10060), recurring every
# ESP32_RECONNECT_COOLDOWN_SEC. That's an accepted, documented cost on
# the Pi where the ESP32 is actually present, but pure waste on a machine
# that will never have one nearby. False skips Esp32Link entirely -
# dispatch() logs what it would have sent instead of touching the socket.
ESP32_LINK_ENABLED = True
ESP32_RFCOMM_PORT = 1  # SPP channel - matches BluetoothSerial's default on the ESP32 side
ESP32_SEND_INTERVAL_SEC = 0.3   # also the de facto link heartbeat - see esp32/ sketch
# ---- Spoken alerts (app/voice.py - phrases and per-warning repeat
# intervals live there, in PROMPTS) ----
VOICE_ALERTS_ENABLED = True
VOICE_MIN_GAP_SEC = 2.0          # silence between any two prompts
VOICE_CONFIRM_SEC = 0.5          # a warning must persist this long before it is spoken
VOICE_CRITICAL_REPEAT_SEC = 4.0  # HIGH-risk prompt repeats while the danger lasts
# Optional natural-sounding voice: path to a Piper .onnx voice model (needs
# the `piper` command, e.g. pip install piper-tts). Empty = espeak-ng/say.
VOICE_PIPER_MODEL = ""
ESP32_RECONNECT_COOLDOWN_SEC = 5.0  # wait after a failed connection attempt...
ESP32_RECONNECT_MAX_COOLDOWN_SEC = 30.0  # ...doubling on each further failure, up to this
# Each attempt ties up the Pi's Bluetooth radio for several seconds while it
# pages the ESP32 - shared with a Bluetooth speaker (audio stutter) and,
# on the Pi's combo chip, with Wi-Fi. Backing off keeps an ESP32 that is
# switched off from degrading the rest of the system.
ESP32_SEND_FAILURE_TOLERANCE = 3    # consecutive send failures before tearing down + reconnecting
                                     # (a single slow send is often just a transient hiccup, not a
                                     # real disconnect - see Esp32Link.send() in alerts.py)


# --------------------------------------------------------------------------
# Quick experiments without editing this file - environment variables
# override the settings above for one run, e.g.:
#     DG_DISPLAY=0 python -m app.main
#     DG_CAMERA_FPS=15 DG_DISPLAY_SCALE=0.5 python -m app.main
# --------------------------------------------------------------------------
_ENV_OVERRIDES = {
    "DG_DISPLAY": ("DISPLAY_ENABLED", bool),
    "DG_DISPLAY_SCALE": ("DISPLAY_SCALE", float),
    "DG_DISPLAY_EVERY": ("DISPLAY_EVERY_N_FRAMES", int),
    "DG_CAMERA_FPS": ("CAMERA_FPS", int),
    "DG_YOLO": ("YOLO_ENABLED", bool),
    "DG_VOICE": ("VOICE_ALERTS_ENABLED", bool),
    "DG_16X9": ("YOLO_USE_16X9_MODEL", bool),
    "DG_ESP32": ("ESP32_LINK_ENABLED", bool),
    "DG_LOG": ("CONSOLE_LOG_ENABLED", bool),
    "DG_WEB": ("WEB_VIEW_ENABLED", bool),
    "DG_WEB_FPS": ("WEB_VIEW_FPS", int),
    "DG_WEB_WIDTH": ("WEB_VIEW_WIDTH", int),
    "DG_WEB_QUALITY": ("WEB_VIEW_JPEG_QUALITY", int),
}
for _var, (_name, _type) in _ENV_OVERRIDES.items():
    if _var in os.environ:
        _raw = os.environ[_var].strip()
        globals()[_name] = (_raw.lower() not in ("0", "false", "no", "off")) if _type is bool else _type(_raw)
        if _name == "YOLO_USE_16X9_MODEL" and globals()[_name]:
            YOLO_NCNN_PATH = os.path.join(MODELS_DIR, "best_384x640_ncnn_model")
            YOLO_IMG_SIZE = (384, 640)
        print(f"[config] {_name} = {globals()[_name]!r}  (from {_var})")

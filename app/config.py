"""Every setting and file path of the app.

Any DG_* environment variable listed at the bottom overrides a setting for
one run, e.g. DG_DISPLAY=0 python -m app.main
"""

import os
import sys

# ---- Paths ----
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")

YOLO_MODEL_PATH = os.path.join(MODELS_DIR, "best.pt")
YOLO_NCNN_PATH = os.path.join(MODELS_DIR, "best_ncnn_model")   # used when present; re-export after changing best.pt
FACE_LANDMARKER_MODEL_PATH = os.path.join(MODELS_DIR, "face_landmarker.task")
FACE_DETECTOR_MODEL_PATH = os.path.join(MODELS_DIR, "blaze_face_short_range.tflite")
SESSION_DB_PATH = os.path.join(DATA_DIR, "driverguardian.db")

# ---- Camera ----
CAMERA_SOURCE = "auto"      # "auto" (Pi camera if available), "csi" or "usb"
CAMERA_INDEX = 0            # USB webcam number on a laptop
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
TARGET_FPS_PREFERRED = 30   # USB webcams
CAMERA_FPS = 20             # Pi camera
CAMERA_NOIR = True          # NoIR colour tuning, removes the infrared red cast
CAMERA_SENSOR = "imx219"
CAMERA_GRAYSCALE = False    # grey image from the ISP (the model was trained on colour)

# ---- Display and dashboard ----
DISPLAY_ENABLED = not sys.platform.startswith("linux")   # local preview window; on the Pi use the dashboard
DISPLAY_SCALE = 1.0
WEB_VIEW_ENABLED = True
DASHBOARD_PIN = "1234"      # protects the dashboard controls; change before a demo
WEB_VIEW_HOST = "0.0.0.0"
WEB_VIEW_PORT = 8080
WEB_VIEW_FPS = 10
WEB_VIEW_WIDTH = 1280
WEB_VIEW_JPEG_QUALITY = 80
WEB_STATUS_INTERVAL_SEC = 0.2
WEB_HISTORY_INTERVAL_SEC = 0.25
WEB_HISTORY_SEC = 600       # live chart history (10 minutes)
SESSION_HISTORY_ENABLED = True
SESSION_HISTORY_KEEP = 20   # sessions kept in the database

APP_NICE = 10               # lower CPU priority so the desktop, audio and Bluetooth stay responsive

# ---- Calibration ----
CALIBRATION_SEC = 3.0

# ---- Eyes ----
EAR_CLOSED_RATIO = 0.80     # closed below 80 % of the driver's own baseline
EAR_SMOOTHING_FRAMES = 3
EAR_MICROSLEEP_SEC = 1.0
EAR_SLEEPING_SEC = 2.5
EAR_SUPPRESS_PITCH_DOWN_DEG = 20.0   # head this far down: eyes look closed, so they are ignored
BLINK_WINDOW_SEC = 5.0
BLINK_RATE_DROWSY_THRESHOLD = 6

# ---- Mouth / yawning ----
MAR_SMOOTHING_FRAMES = 3
MAR_YAWN_RATIO = 2.6        # open above 2.6 x the baseline...
MAR_OPEN_MIN = 0.35         # ...and above this absolute value (talking stays under ~0.3)
YAWN_MIN_DURATION_SEC = 3.2
YAWN_RATE_WINDOW_SEC = 10.0
YAWN_RATE_DROWSY_THRESHOLD = 2

# ---- Head pose ----
HEAD_POSE_SMOOTHING_FRAMES = 5
HEAD_LEAN_PITCH_DOWN_DELTA_DEG = 12.0
HEAD_LEAN_PITCH_UP_DELTA_DEG = 11.0
LEAN_IGNORE_WHEN_TURNED_DEG = 20.0   # a turned head fakes pitch, so lean is ignored past this yaw
LEAN_SCORE_CONFIRM_SEC = 0.5
HEAD_LEAN_RECHECK_DELAY_SEC = 5.0    # still leaning this much later -> HIGH
YAW_TURN_DELTA_DEG = 15.0
YAW_TURN_SEVERE_DELTA_DEG = 50.0
HEAD_TURN_SUSTAIN_SEC = 3.0          # looking away this long -> first level
HEAD_TURN_RECHECK_DELAY_SEC = 6.0    # each further step up

# ---- Presence and covered camera ----
NO_FACE_GRACE_SEC = 0.9
PRESENCE_RECOVER_SEC = 0.5
FRAME_STD_BLOCKED_THRESHOLD = 3.0
OBSTRUCTION_CONFIRM_SEC = 0.5        # shorter than NO_FACE_GRACE_SEC, so a covered lens is named as such
OBSTRUCTION_RECOVER_SEC = 0.5
LOW_LIGHT_BRIGHTNESS_THRESHOLD = 60.0   # below this, CLAHE enhancement

# ---- Startup gate: seatbelt, then the alcohol breath test ----
PRE_DRIVE_CHECK_ENABLED = True
ALCOHOL_CHECK_ENABLED = True
ALCOHOL_RATIO = 1.5            # MQ-3 at 1.5 x the clean-air reference -> alcohol
ALCOHOL_RAW_LIMIT = 700        # or this raw reading (0-1023)
ALCOHOL_BREATH_RISE = 1.05     # a breath raises the MQ-3 at least this much
ALCOHOL_BREATH_SETTLE_SEC = 2.0
ALCOHOL_BLOW_MAX_SEC = 10.0    # no breath seen -> ask again
ALCOHOL_RETEST_SEC = 30.0
ALCOHOL_UNO_WAIT_SEC = 8.0
ALCOHOL_SENSOR_MIN_RAW = 15    # below this the MQ-3 is not connected

# ---- Object detection (YOLO) ----
YOLO_ENABLED = True
YOLO_IMG_SIZE = 640
YOLO_INTERVAL_SEC = 0.4
YOLO_INFERENCE_THREADS = max(1, os.cpu_count() - 2)
YOLO_CONF_THRESHOLD = 0.20     # floor inside the model; per-class thresholds below
YOLO_CLASS_CONF_THRESHOLDS = {
    "phone": 0.30,
    "consumption": 0.50,       # eating and drinking
    "seatbelt": 0.27,
    "cigarette": 0.35,
}
YOLO_CLASS_CONF_DEFAULT = 0.35
YOLO_CONFIRM_WINDOW = 3        # a detection counts in 2 of the last 3 results
YOLO_CONFIRM_MIN = 2
MOUTH_PROXIMITY_RADIUS_MULT = 1.5
DRINK_MOUTH_RADIUS_MULT = 2.5  # drinking counts only within this x the mouth width
SEATBELT_ON_CONFIRM_SEC = 0.5
SEATBELT_OFF_CONFIRM_SEC = 5.0
SEATBELT_UNWORN_ESCALATE_SEC = 10.0
PHONE_REPEAT_TRIGGER = 3       # every 3rd time in a session adds a point
CONSUMPTION_REPEAT_TRIGGER = 3

# ---- Risk score ----
SCORE_LOW_MIN = 1
SCORE_MEDIUM_MIN = 2
SCORE_HIGH_MIN = 4

# ---- Logging and requirements ----
CONSOLE_LOG_ENABLED = True
CONSOLE_LOG_INTERVAL_SEC = 1.0
PROFILE_LOG_INTERVAL_SEC = 5.0
RISK_UPDATE_MIN_AVG_HZ = 12.0
RISK_UPDATE_MIN_HZ = 1.0       # no gap over 1 s
RISK_UPDATE_LOG = False        # every classification to logs/ (tools/check_update_rate.py)

# ---- ESP32 (Bluetooth) ----
ESP32_LINK_ENABLED = True
ESP32_MAC_ADDRESS = "08:B6:1F:3B:1A:AA"
ESP32_RFCOMM_PORT = 1
ESP32_SEND_INTERVAL_SEC = 0.3          # also the heartbeat: 6 s of silence stops the car
ESP32_RECONNECT_COOLDOWN_SEC = 5.0     # doubles after each failure...
ESP32_RECONNECT_MAX_COOLDOWN_SEC = 30.0  # ...up to this
ESP32_SEND_FAILURE_TOLERANCE = 3

# ---- Voice ----
VOICE_ALERTS_ENABLED = True
VOICE_MIN_GAP_SEC = 2.0
VOICE_CONFIRM_SEC = 0.5
VOICE_CRITICAL_REPEAT_SEC = 4.0
VOICE_PIPER_VOICE = "en_US-ryan-high"  # in models/piper/ (tools/get_piper_voice.py)

# ---- Arduino Uno: gas sensors and seat vibration ----
ARDUINO_ENABLED = True
ARDUINO_PORT = "auto"
ARDUINO_BAUD = 115200
ARDUINO_WARMUP_SEC = 30
ARDUINO_FAN_SLEEP_SEC = 3.0    # seat vibration after 3 s of sleep...
ARDUINO_FAN_REPEAT_SEC = 10.0  # ...and every 10 s while it lasts
AIR_REF_INIT_SEC = 10.0        # clean-air reference: average of the first 10 s,
AIR_REF_DOWN_SEC = 30.0        # then follows clean air down quickly,
AIR_REF_UP_SEC = 300.0         # up slowly,
AIR_REF_FREEZE_RATIO = 1.2     # and not at all while a reading is 1.2 x above it
SMOKE_RATIO_ON = 1.5
SMOKE_RATIO_OFF = 1.3
SMOKE_RAW_LIMIT = 700
SMOKE_CONFIRM_SEC = 2.0
ALCOHOL_DRIVE_CONFIRM_SEC = 3.0
ALCOHOL_DRIVE_CLEAR_RATIO = 1.3

# ---- One-run overrides from the environment ----
_ENV_OVERRIDES = {
    "DG_DISPLAY": ("DISPLAY_ENABLED", bool),
    "DG_DISPLAY_SCALE": ("DISPLAY_SCALE", float),
    "DG_CAMERA_FPS": ("CAMERA_FPS", int),
    "DG_CAMERA": ("CAMERA_SOURCE", str),
    "DG_CAMERA_INDEX": ("CAMERA_INDEX", int),
    "DG_NOIR": ("CAMERA_NOIR", bool),
    "DG_GRAY": ("CAMERA_GRAYSCALE", bool),
    "DG_YOLO": ("YOLO_ENABLED", bool),
    "DG_VOICE": ("VOICE_ALERTS_ENABLED", bool),
    "DG_ESP32": ("ESP32_LINK_ENABLED", bool),
    "DG_ARDUINO": ("ARDUINO_ENABLED", bool),
    "DG_ARDUINO_PORT": ("ARDUINO_PORT", str),
    "DG_LOG": ("CONSOLE_LOG_ENABLED", bool),
    "DG_RISK_LOG": ("RISK_UPDATE_LOG", bool),
    "DG_PIN": ("DASHBOARD_PIN", str),
    "DG_WEB": ("WEB_VIEW_ENABLED", bool),
    "DG_WEB_FPS": ("WEB_VIEW_FPS", int),
    "DG_WEB_WIDTH": ("WEB_VIEW_WIDTH", int),
    "DG_WEB_QUALITY": ("WEB_VIEW_JPEG_QUALITY", int),
}
for _var, (_name, _type) in _ENV_OVERRIDES.items():
    if _var in os.environ:
        _raw = os.environ[_var].strip()
        globals()[_name] = (_raw.lower() not in ("0", "false", "no", "off")) if _type is bool else _type(_raw)
        _shown = "(set)" if _name == "DASHBOARD_PIN" else repr(globals()[_name])
        print(f"[config] {_name} = {_shown}  (from {_var})")

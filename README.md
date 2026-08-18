# DriverGuardian

Edge-based Driver Monitoring System (DMS): fatigue, distraction, and unsafe-behavior
detection in real time, built to run on a Raspberry Pi 5 with no cloud dependency.

## Architecture

```
                    Camera
                       |
        +--------------+--------------+
        v                             v
MediaPipe Face Mesh            YOLO Nano
   (+ Face Detection              |
    for presence)                 v
        |                  Object Detection
        v                  (phone/seatbelt/
  Face Analysis             cigarette/food/drink)
        |                             |
        +--------------+--------------+
                       v
                Risk Engine
                       v
                  Alert System
                       v
              ESP32 (vibration, buzzer,
              hazard lights, speed control)
```

## Folder structure

```
DriverGuardian/
├── app/
│   ├── main.py            # entry point - wires everything together
│   ├── camera.py          # Phase 1: camera capture
│   ├── face_detector.py   # Phase 2: presence detection
│   ├── face_mesh.py       # Phase 3: 468/478-point landmarks
│   ├── eye_tracker.py     # Phase 4: EAR calculation
│   ├── drowsiness.py      # Phase 5-6: blink + drowsiness rules
│   ├── head_pose.py       # Phase 7: pitch/yaw/roll via solvePnP
│   ├── yolo_detector.py   # Phase 8, 11: object detection
│   ├── risk_engine.py     # Phase 13: fuse everything into a risk level
│   ├── alerts.py          # Phase 14: voice/TTS + ESP32 Bluetooth link
│   ├── config.py          # all thresholds and paths in one place
│   └── utils.py
├── esp32/
│   └── DriverGuardian_ESP32/
│       └── DriverGuardian_ESP32.ino   # Phase 14: ESP32 firmware (buzzer/vibration/LEDs/hazard relay)
├── datasets/               # Phase 9-10: your collected + annotated images
│   ├── train/ valid/ test/
│   └── data.yaml
├── models/
│   ├── yolo11n.pt                       # pretrained (move your existing file here)
│   ├── best.pt                          # your fine-tuned model (after Phase 11)
│   ├── face_landmarker.task             # MediaPipe Tasks API - Face Mesh (committed, no setup needed)
│   └── blaze_face_short_range.tflite    # MediaPipe Tasks API - presence detection (committed)
├── training/
│   ├── train.py            # Phase 11: fine-tune YOLO
│   ├── evaluate.py         # Phase 12: precision/recall/mAP50
│   └── export.py           # Phase 15: Pi-optimized export (ONNX/NCNN)
├── outputs/                 # screenshots, demo captures
├── logs/                    # per-session CSV logs (auto-created)
└── requirements.txt
```

## Setup

```bash
cd DriverGuardian
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Move your existing `yolo11n.pt` into `models/` (the two MediaPipe Tasks
models are already committed in `models/`, nothing to do there).

On a fresh aarch64/ARM64 install (e.g. Raspberry Pi), pip may resolve
`mediapipe` to a different version than on x86_64 - both `0.10.14+` and
`1.0.0+` work fine here, since the app uses the `mp.tasks.vision` API rather
than the legacy `mp.solutions` API that `1.0.0` removed. If you're on
PyTorch's CUDA build by mistake (common on Linux aarch64, since Raspberry Pi
has no NVIDIA GPU at all), install the CPU-only wheel explicitly first:
`pip install torch --index-url https://download.pytorch.org/whl/cpu`.

### Raspberry Pi + CSI camera (ribbon cable, e.g. imx219)

OpenCV has no libcamera support at all, and Pi 5 dropped the legacy V4L2
camera stack entirely - so `cv2.VideoCapture` cannot read frames from a CSI
camera on a Pi 5 (it'll open, but every read fails). `camera.py` auto-detects
and uses `picamera2` (libcamera-based) instead when it's importable, falling
back to `cv2.VideoCapture` otherwise (USB webcams, or this repo's own
non-Pi dev environment). `picamera2` depends on system libcamera bindings
that only exist on Pi OS, so it's never a pip/requirements.txt dependency -
get it visible inside your venv like this:

```bash
python3 -c "import picamera2"                  # check if it's already installed system-wide
sudo apt update && sudo apt install -y python3-picamera2   # if the above failed
```

Then let your existing venv see it (recreating the venv isn't necessary -
just flip the flag in its config):

```bash
sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' .venv/pyvenv.cfg
source .venv/bin/activate
python -c "from picamera2 import Picamera2; print('picamera2 OK')"
```

If you're on a USB webcam instead, none of this is needed - `cv2.VideoCapture`
already handles it.

## ESP32 (Bluetooth link to buzzer/vibration/LEDs/hazard relay)

The Pi talks to the ESP32 over classic Bluetooth (SPP), sending a line like
`HIGH,SLEEP\n` on a fixed interval - see `app/alerts.py`'s module docstring
for the full wire protocol. **Board requirement:** a classic ESP32 (e.g.
"ESP32 Dev Module" / WROOM-32). ESP32-S3/-C3/-S2 don't have classic
Bluetooth (BLE only) and can't run this sketch unmodified.

### 1. Wire it up

| Signal | ESP32 pin | Notes |
|---|---|---|
| Buzzer | GPIO 25 | Piezo/active buzzer, or through a transistor if it draws more than the pin can source |
| Seat vibration motor | GPIO 26 | Through a transistor/MOSFET - never drive a motor directly off a GPIO |
| Green LED (SAFE) | GPIO 27 | With a current-limiting resistor |
| Amber LED (LOW/MEDIUM) | GPIO 14 | " |
| Red LED (HIGH) | GPIO 13 | " |
| Hazard-lights relay | GPIO 33 | Through a relay module - isolates the ESP32 from the vehicle's 12V hazard circuit |
| Bluetooth-connected status | GPIO 2 | Onboard LED on most ESP32 DevKits, no wiring needed |

### 2. Flash the firmware

1. Arduino IDE: install the ESP32 board package (`esp32` by Espressif Systems, via Boards Manager) if you haven't already.
2. Open `esp32/DriverGuardian_ESP32/DriverGuardian_ESP32.ino`.
3. Tools > Board: select a plain "ESP32 Dev Module" (not S3/C3/S2).
4. Upload. Open the Serial Monitor (115200 baud) - you should see
   `Bluetooth SPP started as 'DriverGuardian_ESP32' - waiting for the Pi...`.

### 3. Pair it with the Pi

```bash
bluetoothctl
power on
agent on
default-agent
scan on
# wait for "DriverGuardian_ESP32" to show up, note its MAC address (AA:BB:CC:DD:EE:FF)
scan off
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
exit
```

Bind it to a serial device node the Python side can open directly:

```bash
sudo rfcomm bind rfcomm0 AA:BB:CC:DD:EE:FF 1
```

That creates `/dev/rfcomm0` (matches `config.ESP32_SERIAL_PORT`). `rfcomm
bind` doesn't survive a reboot by default - re-run it after a Pi restart, or
add it to a startup script/systemd unit if you want it automatic.

### 4. Run it

```bash
python -m app.main
```

`app/alerts.py` connects lazily and never crashes the app if the ESP32 isn't
there - it just prints `[ESP32 -> ] (not connected) ...` and keeps retrying
every `ESP32_RECONNECT_COOLDOWN_SEC`. If the link genuinely drops mid-session
(Pi Bluetooth issue, ESP32 out of range, power loss), the ESP32 firmware
itself notices the silence after `BT_TIMEOUT_MS` and fails safe on its own
(flowchart Case 8: "Bluetooth Failure -> HIGH -> Safe stop mode") - it
doesn't wait around for a Pi that may be the thing that's broken.

## Running

```bash
python -m app.main
```

- Look straight at the camera with eyes open for the 3-second calibration.
- Live status panel shows every signal changing in real time (EAR, head pitch/yaw,
  blink rate, YOLO detections, current risk score).
- Console prints a live log line every 0.5s; a full CSV log is saved per session
  under `logs/`.
- Press `r` to recalibrate at any time, `q` to quit.

## Phase status

| Phase | Deliverable | Status |
|---|---|---|
| 1 | Environment setup, camera verified | Done |
| 2 | Face detection (presence) | Done |
| 3 | Face Mesh landmarks | Done |
| 4 | Eye tracking (EAR) | Done |
| 5 | Blink detection | Done |
| 6 | Drowsiness rules | Done |
| 7 | Head pose (solvePnP) | Done |
| 8 | YOLO pretrained sanity check | Done (uses COCO classes as an approximation) |
| 9 | Dataset collection | **Your task** - not automatable |
| 10 | Annotation (Roboflow/CVAT) | **Your task** |
| 11 | Fine-tune YOLO | Script ready (`training/train.py`) - needs your dataset |
| 12 | YOLO evaluation | Script ready (`training/evaluate.py`) |
| 13 | Risk engine | Done - scored, supports combined-condition escalation |
| 14 | Alert system | Done - voice/TTS + real ESP32 Bluetooth link (`alerts.py`, `esp32/`) |
| 15 | Raspberry Pi optimization | Export script ready (`training/export.py`); test FPS on-device |

## Why "seatbelt" and "cigarette" show as `None` right now

COCO (the dataset the pretrained `yolo11n.pt` was trained on) doesn't include
seatbelt or cigarette classes at all - only phone-like ("cell phone") and
drink-like ("bottle", "cup") objects have a reasonable pretrained approximation.
Real seatbelt/cigarette/food detection needs your own annotated dataset and a
fine-tuned model (Phases 9-11). Until `models/best.pt` exists, those two fields
report `None` (meaning "not yet supported") rather than `False`, so the risk
engine correctly treats them as unknown instead of silently assuming "safe".

## Next steps for you

1. Move `yolo11n.pt` into `models/` and run `python -m app.main` to confirm
   Phases 1-8 + 13-14 work end-to-end with live video.
2. Start collecting images for Phase 9 (see the diversity checklist in the
   original spec: different people, lighting, angles, occlusions, day/night).
3. Annotate in Roboflow (you already have it connected) and export in YOLO
   format into `datasets/`.
4. Fill in `datasets/data.yaml` with your final class names.
5. Run `training/train.py`, then `training/evaluate.py` to check mAP50.
6. Copy the resulting `best.pt` into `models/` - `yolo_detector.py` will pick
   it up automatically on the next run, no code changes needed.
7. Once on the Raspberry Pi, run `training/export.py --format ncnn` (or onnx)
   and benchmark FPS to confirm you're hitting the 20+ FPS target.

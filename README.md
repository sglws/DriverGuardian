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
│   ├── yolo_detector.py   # Phase 8, 11: object detection (runs in its own process)
│   ├── yolo_service.py    # entry point of that YOLO process
│   ├── web_view.py        # monitoring dashboard server (http://<pi>.local:8080)
│   ├── web/               # dashboard page: index.html, style.css, app.js
│   ├── risk_engine.py     # Phase 13: fuse everything into a risk level
│   ├── alerts.py          # Phase 14: routes risk to voice + ESP32 Bluetooth link
│   ├── voice.py           # spoken alerts: phrases, chimes, pacing
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
│   ├── best.pt                          # fine-tuned (Phase 11): Drinking/Eating/Phone/Seatbelt/Smoking
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
source .venv/bin/activate     # MacOs
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

### Voice alerts (Pi)

Spoken alerts use **Piper** (natural, offline neural voice) and play through
the desktop's default audio output (a Bluetooth speaker works - pick it from
the volume icon). One-time setup:

```bash
pip install piper-tts                 # (already in requirements.txt)
python tools/get_piper_voice.py       # downloads the voice set in VOICE_PIPER_VOICE (~60 MB)
sudo apt install -y espeak-ng         # fallback voice if Piper isn't installed
```

Each alert is a short chime plus one fixed phrase (see `PROMPTS` in
`app/voice.py`), rendered once into `assets/voice_cache/` on first start
(~10 s on the Pi with Piper) and played from the cache afterwards. To change
the voice, set `VOICE_PIPER_VOICE` in `app/config.py` (e.g. `en_US-amy-medium`,
`en_US-ryan-high`), download it with `tools/get_piper_voice.py <voice>` and
restart. Voice files live in `models/piper/` and are not committed (too large).

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

Paste that MAC address into `config.ESP32_MAC_ADDRESS`.

`app/alerts.py` connects with a **raw `AF_BLUETOOTH`/`BTPROTO_RFCOMM` socket
straight to that MAC address** - not `rfcomm bind`/`/dev/rfcommX`, which has
proven unreliable on some BlueZ versions. No extra setup beyond pairing +
trusting above; nothing needs to survive a reboot separately, since the app
opens the connection itself each time it starts.

**Important:** don't also run a separate always-on script/service (e.g. a
systemd unit) that connects to the ESP32 on its own. Classic Bluetooth SPP
only accepts one connected client at a time - if something else is already
holding that connection, the app's own connection attempt will be refused.
Only one thing should ever be connecting to the ESP32 at a time, and it
should be the app itself.

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
- Watch it live in a browser (below). The overlay shows every signal changing in
  real time (EAR, head pitch/yaw, blink rate, YOLO detections, current risk score).
- Console prints a live log line every second; a full CSV log is saved per session
  under `logs/`.
- Recalibrate with the **Recalibrate** button on the live page; stop with Ctrl+C.

### Watching it live (remote testing)

The app serves its own live view. On any device on the same network open:

```
http://pi5.local:8080        (use your Pi's hostname, or the IP printed at startup)
```

The monitoring dashboard shows:

- the live camera view (face mesh + object detections), full-screen capable
- the current risk level and reason, and how long it has lasted
- live driver signals: eyes, blinks, mouth/yawning, head direction, phone,
  eating/drinking, smoking, seatbelt, driver presence and lighting
- trends for the last 1/5/10 minutes: risk timeline, eye openness (EAR),
  mouth opening (MAR) and head pose - hover or use the arrow keys to read
  values, or switch any chart to a table
- requirement checks (update rate >= 12 Hz, longest gap <= 1 s), time per
  frame, CPU temperature/throttling, load and memory, YOLO / ESP32 / voice status
- session summary (time at each risk level, alerts by type) and an event log
  (risk changes, spoken alerts, detections, link changes)
- **Recalibrate** and **Snapshot** buttons, light/dark theme

Several people can watch at once; video is only encoded while someone is watching.
Everything is served by the app itself - no internet connection needed.

**Don't watch the app through remote-desktop screen sharing** (Raspberry Pi
Connect's screen sharing, VNC). The Pi 5 has no hardware video encoder, so it
re-encodes its whole desktop in software, and a live camera window makes the
remote desktop lag and stutter. The app's own window is therefore off by
default on the Pi (it stays on on a Mac/PC). Use Pi Connect's *remote shell* or `ssh dms@pi5.local` to run commands,
and the browser to watch.

- A monitor plugged straight into the Pi can still show the window:
  `DG_DISPLAY=1 python -m app.main` (keys: `r` recalibrate, `q` quit).
- A network cable is more reliable than Wi-Fi for long test sessions: the Pi's
  Wi-Fi shares its radio with Bluetooth (the ESP32 link).

## Testing the requirements

Each measurable requirement has a tool that prints PASS/FAIL. Stop the app
before the tools that use the camera or the ESP32 (`systemctl --user stop
driverguardian.service` if it runs as a service).

| Requirement | Command (on the Pi) | Notes |
|---|---|---|
| Eye state and yawning >= 90% | `python tools/face_accuracy_test.py --condition normal`<br>`python tools/face_accuracy_test.py --condition dim`<br>`python tools/face_accuracy_test.py --report logs/face_accuracy_*.csv` | Guided script (beeps); 2+ people x normal and dim light. Uses balanced accuracy for eyes, per-event accuracy for yawns. |
| Detection delay <= 1 s | `python tools/detection_delay_test.py --object phone`<br>(`--object consumption`, `--object cigarette`) | Raise the object at each beep. Onset is found by YOLO on every recorded frame, so the tester's reaction time doesn't count. |
| Update rate >= 12 Hz average, no gap > 1 s | `DG_RISK_LOG=1 python -m app.main` (monitor, then quit)<br>`python tools/check_update_rate.py` | Calibration/waiting pauses are excluded (logged as separate segments). Also live on the dashboard. |
| Bluetooth latency p99 <= 50 ms, max <= 100 ms | `python tools/bt_latency_benchmark.py --audio --label "wifi + speaker"` | Needs the `esp32/latency_echo` sketch on the ESP32. `--audio` plays the speaker during the run (shared radio). `python tools/plot_latency.py` makes the report figure. |
| 16:9 YOLO model equivalent | `python tools/compare_yolo_models.py --seconds 90` | Show phone, cup/bottle, food, cigarette (or a pen), seatbelt on/off. Saves frames where the models disagree. |

## Run at boot

`systemd/driverguardian.service` runs the app automatically once the Pi
boots to the desktop, and restarts it if it ever crashes mid-drive instead
of leaving monitoring silently dead. It's a **systemd `--user` service**
(not a system-level one) specifically so it starts inside the desktop
auto-login session and correctly inherits `DISPLAY`/`XAUTHORITY` for
`cv2.imshow()` - a system-level unit would need those set manually and
tends to fight the GUI session for camera/display access.

Requires desktop auto-login enabled (`sudo raspi-config` -> System Options
-> Boot / Auto Login -> Desktop Autologin).

```bash
# Edit WorkingDirectory/ExecStart in the unit file first if your repo
# isn't cloned to ~/DriverGuardian
mkdir -p ~/.config/systemd/user
cp systemd/driverguardian.service ~/.config/systemd/user/
loginctl enable-linger "$USER"   # lets the user service start at login, not just when you SSH in
systemctl --user daemon-reload
systemctl --user enable --now driverguardian.service
```

Check on it:

```bash
systemctl --user status driverguardian.service
journalctl --user -u driverguardian.service -f   # live log tail
```

To stop it starting at boot (e.g. while actively debugging):

```bash
systemctl --user disable --now driverguardian.service
```

Don't also run a separate service that connects to the ESP32 - see the
Bluetooth section above for why.

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
| 11 | Fine-tune YOLO | Done - `models/best.pt` trained (Drinking/Eating/Phone/Seatbelt/Smoking) |
| 12 | YOLO evaluation | Script ready (`training/evaluate.py`) - run it to check per-class mAP/precision/recall |
| 13 | Risk engine | Done - scored, supports combined-condition escalation |
| 14 | Alert system | Done - voice/TTS + real ESP32 Bluetooth link (`alerts.py`, `esp32/`) |
| 15 | Raspberry Pi optimization | Export script ready (`training/export.py`); test FPS on-device |

## Seatbelt detection: presence-inferred, not a direct read

`models/best.pt` (Drinking/Eating/Phone/Seatbelt/Smoking) only has a
"Seatbelt" class for the belt *worn/visible* - there's no negative class,
since you can't draw a bounding box around an object that isn't there. So
`seatbelt_off` isn't read directly off a detection: `DetectionConfirmer`
(`app/yolo_detector.py`) tracks how long it's been since the belt was last
seen, and infers "off" once that exceeds `SEATBELT_ABSENCE_INFER_SEC`
(8s, in `config.py`). It stays `None` (unknown) until the belt has been
confirmed visible at least once. If `cigarette` still needs a wider dataset
for reliable "Smoking" detection, it reads `None` too (not `False`) so the
risk engine treats it as unknown rather than silently assuming "safe".

## Next steps for you

1. Run `python -m app.main` and confirm the full pipeline works end-to-end
   with live video, now that `models/best.pt` is in place.
2. Run `training/evaluate.py` against `models/best.pt` to check per-class
   mAP/precision/recall - if any class underperforms, more training data for
   just that class (see the diversity checklist: angles, lighting, occlusion,
   day/night) is usually the fix, not a different model architecture.
3. If you retrain with additional/renamed classes, update
   `datasets/data.yaml` to match and confirm `app/yolo_detector.py`'s
   substring matching still picks them up correctly.
4. Once on the Raspberry Pi, run `training/export.py --format ncnn` (or onnx)
   and benchmark FPS to confirm you're hitting the 20+ FPS target.

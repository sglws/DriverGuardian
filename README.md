# DriverGuardian

AI-Powered Driver Monitoring System with Real-Time Vehicle Intervention.

A camera watches the driver and two gas sensors watch the cabin air. A risk engine
rates the risk as SAFE, LOW, MEDIUM or HIGH and speaks a short warning. The risk
level is sent over Bluetooth to an ESP32 that slows the car down. At HIGH, the car
pulls over to the right and stops by itself. Everything runs on a Raspberry Pi 5,
with no cloud.

```
camera ─> face landmarks ─> eyes, mouth, head pose ─┐
       └> YOLO (own process) ─> phone, eating/drinking, smoking, seatbelt ─┤
Arduino Uno ─> MQ-3 alcohol, MQ-2 smoke ────────────────────────────────────┤
                                                                     risk engine
                     voice alert <─┬─ seat vibration (Uno) <─┬──────────┘
                                   └─ ESP32: speed, pull-over, emergency stop
```

## Project layout

```
app/
  main.py          the main loop (python -m app.main)
  config.py        every setting and threshold
  utils.py         small shared helpers
  vision/          camera, face landmarks, eyes, mouth, head pose, drowsiness, YOLO
  risk/            risk engine, alcohol breath test and cabin air
  outputs/         voice alerts, ESP32 Bluetooth link, Arduino Uno link
  dashboard/       web server, session recording, database, dashboard tests, web/ (page)
firmware/
  uno/             Arduino Uno sketch (gas sensors, seat vibration)
  esp32/           ESP32 sketches (the car, and a Bluetooth latency echo)
models/            best.pt and its NCNN export, MediaPipe face models
tools/             diagnostics and measurements
training/          train, evaluate and export the object detector
systemd/           service file to start the app at boot
```

## Setup (Raspberry Pi 5)

```bash
git clone https://github.com/sglws/DriverGuardian.git && cd DriverGuardian
python3 -m venv .venv
sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' .venv/pyvenv.cfg
source .venv/bin/activate
sudo apt install -y python3-picamera2 espeak-ng
pip install -r requirements.txt
python tools/get_piper_voice.py        # the voice (about 60 MB, not in git)
```

The Pi camera is read through `picamera2`, which only exists as a system package;
that is why the virtual environment sees the system packages. On a laptop, a USB
webcam works with no extra setup.

## Running

```bash
python -m app.main
```

Look straight at the camera for the 3-second calibration. The drive starts once the
seatbelt is seen and the breath test is passed. Open the dashboard from any device
on the same network: `http://<pi-name>.local:8080`. Watching needs nothing; the
controls ask for `DASHBOARD_PIN` (in `app/config.py`, change it before a demo).

Settings live in `app/config.py`. Any `DG_*` variable at the bottom of that file
overrides one for a single run, for example `DG_DISPLAY=0` or `DG_ESP32=0`.

### Start at boot

```bash
mkdir -p ~/.config/systemd/user
cp systemd/driverguardian.service ~/.config/systemd/user/
systemctl --user enable --now driverguardian.service
```

Update: `systemctl --user stop driverguardian && git pull && systemctl --user start driverguardian`.

## ESP32 (the car)

1. Flash `firmware/esp32/DriverGuardian_ESP32` with the Arduino IDE (board: ESP32 Dev
   Module; it needs classic Bluetooth, so not an S3 or C3).
2. Pair it once with the Pi:
   `bluetoothctl` → `scan on` → `pair <MAC>` → `trust <MAC>` → `exit`.
3. Put the MAC address in `ESP32_MAC_ADDRESS` in `app/config.py`.

The Pi sends `RISK,CASE` every 0.3 s; the ESP32 answers with a `TEL,...` telemetry
line every 0.25 s (motor speeds, distances, edge sensors), shown on the dashboard.
If the ESP32 hears nothing for 6 s, it pulls over on its own. Nothing else may hold
the ESP32's Bluetooth connection while the app runs.

## Arduino Uno (gas sensors and seat vibration)

| Part | Uno pin |
|---|---|
| MQ-3 alcohol, AO | A0 |
| MQ-2 smoke, AO | A1 |
| BTS7960 seat motor, RPWM | 6 |

Flash `firmware/uno/DriverGuardian_Uno` and plug the Uno into the Pi by USB; the app
finds it by itself. The sensors warm up for 30 s, then the readings are compared with
a clean-air reference, so start in clean air. If the Uno is not found, run
`python tools/check_uno.py`.

## Tests and measurements

| Requirement | How |
|---|---|
| Eye state and yawning ≥ 90 % | Dashboard → Test → Face accuracy |
| Detection delay ≤ 1 s | Dashboard → Test → Detection delay |
| Risk updates ≥ 12 Hz, no gap over 1 s | Live on the dashboard, or `DG_RISK_LOG=1 python -m app.main` then `python tools/check_update_rate.py` |
| Bluetooth round trip | `python tools/bt_latency_benchmark.py` (needs the `latency_echo` sketch), then `python tools/plot_latency.py` |
| Compare two models | `python tools/compare_yolo_models.py --models main 3nov` |

## Training the object detector

```bash
python training/train.py path/to/data.yaml   # Roboflow export, on a PC with a GPU
cp runs/detect/<run>/weights/best.pt models/best.pt
python training/export.py                    # NCNN export for the Pi
```

`train.py` prints the per-class test results and the best confidence of each class,
the starting values for `YOLO_CLASS_CONF_THRESHOLDS` in `app/config.py`.

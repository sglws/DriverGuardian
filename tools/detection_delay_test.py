"""Measure the object-detection delay: object appears -> app confirms it.

Requirement: detection delay not exceeding 1 second.

How it works
  * The app's real detection path runs live: the YOLO process at
    YOLO_INTERVAL_SEC with its 2-of-3 confirmation - exactly what the app
    does while monitoring.
  * A beep tells the tester to bring the object into view; every camera
    frame is recorded with its timestamp.
  * Afterwards, YOLO is run on EVERY recorded frame (offline, same model and
    thresholds) to find the first frame in which the object is actually
    visible - the true onset, independent of the tester's reaction time.
  * delay = time the live app confirmed the object - onset frame time.

Stop the app first (the camera can only be opened by one program).

Usage (on the Pi):
    python tools/detection_delay_test.py                    # phone, 5 trials
    python tools/detection_delay_test.py --object consumption --trials 8
Objects: phone, consumption (cup/bottle/food at the mouth), cigarette.
Each trial: ~4 s object hidden, then beep -> show it and hold it ~5 s.
"""
import argparse
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app import config, utils  # noqa: E402

HIDE_SEC, SHOW_SEC, PRE_ROLL_SEC = 4.0, 5.0, 0.5


class Beeper:
    """Audible cue through the speaker (the terminal bell is often silent over SSH)."""

    def __init__(self):
        self.player = next((shutil.which(p) for p in ("pw-play", "paplay", "aplay", "afplay") if shutil.which(p)), None)
        self.path = os.path.join(tempfile.gettempdir(), "dg_delay_beep.wav")
        rate = 22050
        with wave.open(self.path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
            n = int(0.25 * rate)
            w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 1320 * i / rate)
                                                         * min(1, (n - i) / 800))) for i in range(n)))

    def beep(self):
        print("\a", end="", flush=True)
        if self.player:
            subprocess.Popen([self.player, self.path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser(description="Measure object detection delay.")
    ap.add_argument("--object", choices=("phone", "consumption", "cigarette"), default="phone")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--limit", type=float, default=1.0, help="requirement in seconds (default 1.0)")
    args = ap.parse_args()

    from app.camera import Camera
    from app.yolo_detector import YoloProcess
    camera = Camera()
    yolo = YoloProcess()
    if not yolo.available:
        sys.exit("YOLO is not available (no model / ultralytics not installed).")
    face_mesh = None
    if args.object != "phone":          # drink/food/cigarette only count near the mouth
        from app.face_mesh import FaceMeshWrapper
        face_mesh = FaceMeshWrapper()
    beeper = Beeper()

    def mouth_roi(frame):
        if face_mesh is None:
            return None
        h, w = frame.shape[:2]
        lm, _ = face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        return utils.mouth_roi(lm, w, h, config.MOUTH_PROXIMITY_RADIUS_MULT) if lm is not None else None

    print("Starting the YOLO process...")
    t_wait = time.monotonic()
    while yolo.health(time.monotonic())["state"] == "starting" and time.monotonic() - t_wait < 60:
        ok, frame = camera.read()
        yolo.submit(frame, None)
        yolo.get_latest()
        time.sleep(0.05)

    trials = []
    last_submit = 0.0
    try:
        for n in range(1, args.trials + 1):
            print(f"\nTrial {n}/{args.trials}: HIDE the {args.object} - keep it out of the camera view...")
            rec, confirmed_at, cue_at = [], None, None
            t0 = time.monotonic()
            while True:
                now = time.monotonic()
                el = now - t0
                if el >= HIDE_SEC + SHOW_SEC:
                    break
                if cue_at is None and el >= HIDE_SEC:
                    cue_at = now
                    beeper.beep()
                    print(f"  >>> SHOW the {args.object} NOW and hold it in view <<<")
                ok, frame = camera.read()
                if not ok:
                    continue
                t_frame = time.monotonic()
                roi = mouth_roi(frame)
                if now - last_submit >= config.YOLO_INTERVAL_SEC and yolo.submit(frame, roi):
                    last_submit = time.monotonic()
                state = yolo.get_latest()
                if cue_at is not None and confirmed_at is None and state.get(args.object):
                    confirmed_at = time.monotonic()
                if el >= HIDE_SEC - PRE_ROLL_SEC:                # keep frames around the cue only
                    small = cv2.resize(frame, (640, round(frame.shape[0] * 640 / frame.shape[1])),
                                       interpolation=cv2.INTER_AREA)
                    ok, jpg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    s = 640 / frame.shape[1]
                    rec.append((t_frame, jpg, tuple(v * s for v in roi) if roi else None))
            trials.append({"cue": cue_at, "confirmed": confirmed_at, "frames": rec})
            print("  put it away again" if n < args.trials else "  done")
            if state.get(args.object) and n < args.trials:
                time.sleep(2.0)                                  # let the confirmation clear
    finally:
        camera.release()
        yolo.close()
        if face_mesh:
            face_mesh.close()

    print("\nFinding the true onset frame of each trial (YOLO on every recorded frame)...")
    from app.yolo_detector import YoloDetector
    det = YoloDetector()
    results = []
    for n, tr in enumerate(trials, 1):
        onset = None
        for t_frame, jpg, roi in tr["frames"]:
            if t_frame < tr["cue"] - PRE_ROLL_SEC:
                continue
            frame = cv2.imdecode(np.frombuffer(jpg.tobytes(), np.uint8), cv2.IMREAD_COLOR)
            if det.detect(frame, mouth_roi=roi)[args.object]:
                onset = t_frame
                break
        delay = (tr["confirmed"] - onset) if (onset is not None and tr["confirmed"] is not None) else None
        results.append((n, onset, tr, delay))
        on = f"{onset - tr['cue']:+.2f} s after the beep" if onset is not None else "never visible"
        if delay is not None:
            print(f"  trial {n}: object visible {on}, confirmed {delay:.2f} s later")
        elif onset is not None:
            print(f"  trial {n}: object visible {on}, NOT confirmed within {SHOW_SEC:.0f} s")
        else:
            print(f"  trial {n}: object never detected in any frame (out of view? wrong object?)")

    delays = [d for *_, d in results if d is not None]
    print(f"\n=== Detection delay: {args.object} ({len(delays)}/{len(results)} trials measured) ===")
    if not delays:
        sys.exit("No trial could be measured.")
    print(f"mean {sum(delays) / len(delays):.2f} s | median {sorted(delays)[len(delays) // 2]:.2f} s | "
          f"max {max(delays):.2f} s")
    missed = sum(1 for _, onset, tr, d in results if onset is not None and d is None)
    ok = max(delays) <= args.limit and missed == 0
    print(f"Requirement <= {args.limit:g} s: {'PASS' if ok else 'FAIL'}"
          + (f"  ({missed} visible object(s) never confirmed)" if missed else ""))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

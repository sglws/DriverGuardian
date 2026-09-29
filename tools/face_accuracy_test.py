"""Measure the accuracy of eye-state (open/closed) and yawn detection.

Requirement: "The computer vision pipeline shall detect the driver's eye state
(open/closed) and yawning with an accuracy of at least 90% across variable
daytime and low-light cabin conditions."

This runs the app's REAL perception path - same camera, low-light
enhancement, MediaPipe FaceLandmarker, EyeTracker/MouthTracker smoothing,
calibrated baselines and DrowsinessDetector rules - while a guided script
tells the tester what to do. What the tester was told to do is the ground
truth; what the app decided is compared against it on every frame.

Guided script (one round, ~31 s; default 3 rounds per run):
    OPEN    eyes open, mouth closed           6 s
    CLOSED  eyes closed (count to 4)          4 s
    OPEN    eyes open, blink normally         5 s
    TALK    talk / count out loud             6 s   <- must NOT count as a yawn
    YAWN    yawn: mouth wide, hold            6 s
    OPEN    relax                             4 s
A beep (terminal bell) marks every step change, so the CLOSED step works
without watching the screen. The first GUARD_SEC of each step is excluded
from scoring - that's the tester's reaction time, not a detection error.

Scoring
  Eye state  per frame, over OPEN/CLOSED/TALK steps (YAWN excluded: eyes
             naturally squint during a yawn, so its eye label is ambiguous).
             Frames where MediaPipe found no face count as the app's actual
             output (eyes "open"), i.e. as errors on CLOSED steps.
             Accuracy AND balanced accuracy are reported: open-eye frames
             outnumber closed ones ~4:1, so plain accuracy alone flatters a
             detector that rarely says "closed".
  Yawning    per event, exactly as the app decides it (mouth open beyond
             MAR_YAWN_RATIO x baseline for >= YAWN_MIN_DURATION_SEC):
             a YAWN step is correct if a yawn registered; an OPEN/TALK step is
             correct if none did. Per-frame mouth-open accuracy is shown too.

Usage (on the Pi, with a display):
    python tools/face_accuracy_test.py --condition normal
    python tools/face_accuracy_test.py --condition dim
    python tools/face_accuracy_test.py --report logs/face_accuracy_*.csv   # combine runs
Press q to abort a run (what was recorded so far is still saved and scored).
"""
import argparse
import csv
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GUARD_SEC = 0.8
SCRIPT = [
    ("OPEN",   "Eyes OPEN, look at the camera, mouth closed", 6.0),
    ("CLOSED", "CLOSE your eyes - count to 4, open at the beep", 4.0),
    ("OPEN",   "Eyes OPEN, blink normally", 5.0),
    ("TALK",   "TALK / count out loud, eyes open", 6.0),
    ("YAWN",   "YAWN - open mouth wide and hold until the beep", 6.0),
    ("OPEN",   "Relax - eyes open, mouth closed", 4.0),
]
EYE_LABEL = {"OPEN": "open", "CLOSED": "closed", "TALK": "open", "YAWN": ""}
FIELDS = ["condition", "round", "step_id", "step", "t_in_step", "scored", "eye_label", "yawn_label",
          "face_found", "ear", "ear_threshold", "eye_closed_pred", "mar", "mar_threshold",
          "mouth_open_pred", "is_yawning", "looking_down", "brightness", "low_light"]
REQUIREMENT = 0.90


def beep():
    print("\a", end="", flush=True)


def put(frame, text, y, scale=0.8, color=(255, 255, 255)):
    import cv2
    cv2.putText(frame, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 5)
    cv2.putText(frame, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2)


def run_session(condition, rounds, out_path):
    import cv2
    import numpy as np
    from app import config, utils
    from app.camera import Camera
    from app.face_mesh import FaceMeshWrapper
    from app.eye_tracker import EyeTracker
    from app.mouth_tracker import MouthTracker
    from app.head_pose import estimate_pose, HeadPoseTracker
    from app.drowsiness import DrowsinessDetector

    camera = Camera()
    face_mesh = FaceMeshWrapper()
    eye_tracker, mouth_tracker = EyeTracker(), MouthTracker()
    head_pose, drowsiness = HeadPoseTracker(), DrowsinessDetector()

    def perceive():
        """One frame through the app's exact perception path (see main.py)."""
        ret, frame = camera.read()
        if not ret:
            raise RuntimeError("camera read failed")
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = utils.frame_mean_brightness(gray)
        low_light = brightness < config.LOW_LIGHT_BRIGHTNESS_THRESHOLD
        if low_light:
            frame = utils.enhance_low_light(frame)
        landmarks, _ = face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        ear, mar, pitch, yaw = 0.30, 0.5, 0.0, 0.0   # same sentinels as main.py
        if landmarks is not None:
            ear = eye_tracker.update(landmarks, w, h)
            mar = mouth_tracker.update(landmarks, w, h)
            p, y_, _ = estimate_pose(landmarks, w, h)
            if p is not None:
                pitch, yaw = p, y_
        return frame, landmarks is not None, ear, mar, pitch, yaw, brightness, low_light

    rows, aborted = [], False
    try:
        # ---- Calibration: identical to main.py ----
        calib, t0 = [], None
        while True:
            frame, found, ear, mar, pitch, yaw, _, _ = perceive()
            if found:
                t0 = t0 or time.monotonic()
                calib.append((ear, mar, pitch, yaw))
                msg = f"CALIBRATING - look straight, eyes open, mouth closed " \
                      f"({time.monotonic() - t0:.1f}/{config.CALIBRATION_SEC:.0f}s)"
            else:
                msg = "Waiting for face..."
            put(frame, msg, 30, 0.6, (0, 255, 255))
            cv2.imshow("Face accuracy test", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                return rows, True
            if t0 and time.monotonic() - t0 >= config.CALIBRATION_SEC:
                break
        b_ear, b_mar, b_pitch, b_yaw = (float(np.median([c[i] for c in calib])) for i in range(4))
        drowsiness.set_baseline(b_ear)
        drowsiness.set_mouth_baseline(b_mar)
        head_pose.set_baseline(b_pitch, b_yaw)
        print(f"Calibration done. EAR={b_ear:.3f} MAR={b_mar:.3f}")

        # ---- Get ready ----
        t_ready = time.monotonic()
        while time.monotonic() - t_ready < 3.0:
            frame = perceive()[0]
            put(frame, f"Starting in {3 - int(time.monotonic() - t_ready)}... follow the instructions", 30, 0.6)
            cv2.imshow("Face accuracy test", frame)
            cv2.waitKey(1)

        # ---- Guided script ----
        step_id = 0
        for rnd in range(1, rounds + 1):
            for step, instruction, duration in SCRIPT:
                step_id += 1
                beep()
                print(f"[round {rnd}/{rounds}] {step}: {instruction}")
                t_step = time.monotonic()
                while (t_in := time.monotonic() - t_step) < duration:
                    frame, found, ear, mar, pitch, yaw, brightness, low_light = perceive()
                    now = time.monotonic()
                    pose = head_pose.update(pitch, yaw, now, face_found=found)
                    st = drowsiness.update(ear, now, pose["pitch_delta"], mar, face_found=found)
                    rows.append({
                        "condition": condition, "round": rnd, "step_id": step_id, "step": step,
                        "t_in_step": f"{t_in:.3f}", "scored": int(t_in >= GUARD_SEC),
                        "eye_label": EYE_LABEL[step], "yawn_label": int(step == "YAWN"),
                        "face_found": int(found), "ear": f"{ear:.4f}",
                        "ear_threshold": f"{drowsiness.closed_threshold:.4f}",
                        "eye_closed_pred": int(st["eye_closed"]), "mar": f"{mar:.4f}",
                        "mar_threshold": f"{drowsiness.open_mouth_threshold:.4f}",
                        "mouth_open_pred": int(st["mouth_open"]), "is_yawning": int(st["is_yawning"]),
                        "looking_down": int(st["looking_down"]),
                        "brightness": f"{brightness:.1f}", "low_light": int(low_light),
                    })
                    put(frame, f"{instruction}", 32, 0.65, (0, 255, 255))
                    put(frame, f"round {rnd}/{rounds}   {duration - t_in:.1f}s left", 62, 0.6)
                    put(frame, f"app sees: eyes {'CLOSED' if st['eye_closed'] else 'open'}"
                               f"  mouth {'OPEN' if st['mouth_open'] else 'closed'}"
                               f"{'  YAWN' if st['is_yawning'] else ''}"
                               f"{'' if found else '  (no face)'}", frame.shape[0] - 16, 0.6)
                    cv2.imshow("Face accuracy test", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        aborted = True
                        break
                if aborted:
                    break
            if aborted:
                break
        beep()
    finally:
        camera.release()
        face_mesh.close()
        cv2.destroyAllWindows()
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
    return rows, aborted


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "n/a"


def summarize(rows, title):
    print(f"\n===== {title} =====")
    if not rows:
        print("No data.")
        return
    conds = sorted({r["condition"] for r in rows})
    print(f"Conditions: {', '.join(conds)} | frames: {len(rows)} | "
          f"face found: {pct(sum(int(r['face_found']) for r in rows), len(rows))} | "
          f"low-light enhancement active: {pct(sum(int(r['low_light']) for r in rows), len(rows))}")

    # ---- Eye state, per frame ----
    eye = [r for r in rows if r["scored"] in ("1", 1) and r["eye_label"]]
    tp = sum(1 for r in eye if r["eye_label"] == "closed" and int(r["eye_closed_pred"]))
    fn = sum(1 for r in eye if r["eye_label"] == "closed" and not int(r["eye_closed_pred"]))
    tn = sum(1 for r in eye if r["eye_label"] == "open" and not int(r["eye_closed_pred"]))
    fp = sum(1 for r in eye if r["eye_label"] == "open" and int(r["eye_closed_pred"]))
    n = tp + fn + tn + fp
    closed_recall = tp / (tp + fn) if tp + fn else 0.0
    open_recall = tn / (tn + fp) if tn + fp else 0.0
    eye_acc = (tp + tn) / n if n else 0.0
    eye_bal = (closed_recall + open_recall) / 2
    no_face_closed = sum(1 for r in eye if r["eye_label"] == "closed" and not int(r["face_found"]))
    print("\nEYE STATE (per frame)")
    print(f"  frames scored: {n}  (closed {tp + fn}, open {tn + fp})")
    print(f"  confusion:     closed->closed {tp}  closed->open {fn}  open->open {tn}  open->closed {fp}")
    print(f"  closed eyes detected: {pct(tp, tp + fn)}   open eyes correct: {pct(tn, tn + fp)}")
    if no_face_closed:
        print(f"  note: {no_face_closed} of the missed closed-eye frames had no face detected")
    print(f"  accuracy {100 * eye_acc:.1f}%   balanced accuracy {100 * eye_bal:.1f}%")

    # ---- Yawning, per event (step) and per frame ----
    steps = {}
    for r in rows:
        key = (r["condition"], r["round"], r["step_id"])
        s = steps.setdefault(key, {"step": r["step"], "yawn": False})
        s["yawn"] |= bool(int(r["is_yawning"]))
    yawn_steps = [s for s in steps.values() if s["step"] == "YAWN"]
    other_steps = [s for s in steps.values() if s["step"] in ("OPEN", "TALK", "CLOSED")]
    talk_steps = [s for s in steps.values() if s["step"] == "TALK"]
    hit = sum(s["yawn"] for s in yawn_steps)
    false_yawn = sum(s["yawn"] for s in other_steps)
    ev_n = len(yawn_steps) + len(other_steps)
    yawn_acc = (hit + len(other_steps) - false_yawn) / ev_n if ev_n else 0.0
    mouth = [r for r in rows if r["scored"] in ("1", 1)]
    m_ok = sum(1 for r in mouth if int(r["mouth_open_pred"]) == int(r["yawn_label"]))
    print("\nYAWNING (per event)")
    print(f"  yawns detected: {hit}/{len(yawn_steps)}   "
          f"false yawns: {false_yawn}/{len(other_steps)} non-yawn steps "
          f"(talking: {sum(s['yawn'] for s in talk_steps)}/{len(talk_steps)})")
    print(f"  event accuracy {100 * yawn_acc:.1f}%   (mouth-open per-frame accuracy {pct(m_ok, len(mouth))})")

    print(f"\nRequirement >= {REQUIREMENT:.0%}:")
    print(f"  eye state (balanced accuracy): {100 * eye_bal:.1f}%  "
          f"{'PASS' if eye_bal >= REQUIREMENT else 'FAIL'}")
    print(f"  yawning (event accuracy):      {100 * yawn_acc:.1f}%  "
          f"{'PASS' if yawn_acc >= REQUIREMENT else 'FAIL'}")
    if len(yawn_steps) < 10:
        print(f"  (only {len(yawn_steps)} yawn events - combine several runs with --report "
              f"for a figure worth citing)")


def main():
    ap = argparse.ArgumentParser(description="Eye-state and yawn detection accuracy test.")
    ap.add_argument("--condition", default="normal",
                    help="label for this run's lighting/person, e.g. normal, dim, person2_dim")
    ap.add_argument("--rounds", type=int, default=3, help="script repetitions per run (default 3)")
    ap.add_argument("--report", nargs="+", metavar="CSV", help="score existing run CSVs instead of recording")
    args = ap.parse_args()

    if args.report:
        rows = []
        for p in args.report:
            with open(p, newline="") as f:
                rows += list(csv.DictReader(f))
        for cond in sorted({r["condition"] for r in rows}):
            summarize([r for r in rows if r["condition"] == cond], f"condition: {cond}")
        summarize(rows, f"ALL {len(args.report)} run(s) combined")
        return

    from app import config
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    out = os.path.join(config.LOGS_DIR, f"face_accuracy_{time.strftime('%Y%m%d_%H%M%S')}_{args.condition}.csv")
    rows, aborted = run_session(args.condition, args.rounds, out)
    print(f"\nSaved {len(rows)} frames to {out}" + ("  (run aborted early)" if aborted else ""))
    summarize(rows, f"this run ({args.condition})")


if __name__ == "__main__":
    main()

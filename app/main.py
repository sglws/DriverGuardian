"""
main.py
-------
DriverGuardian entry point. Wires together every module in the pipeline:

    Camera -> Face Mesh -> Eye Tracker -> Drowsiness Detector
                        --> Head Pose Tracker
    Camera -> YOLO Detector

    Presence Detector ---+--> Risk Engine --> Alert System

Run from the project root with:
    python -m app.main
"""

import csv
import os
import time
from collections import deque

import cv2
import numpy as np

from app import config, utils
from app.camera import Camera
from app.face_detector import PresenceDetector
from app.face_mesh import FaceMeshWrapper
from app.eye_tracker import EyeTracker
from app.mouth_tracker import MouthTracker
from app.drowsiness import DrowsinessDetector, DrowsinessLevel
from app.head_pose import estimate_pose, HeadPoseTracker
from app.yolo_detector import YoloDetector, DetectionConfirmer
from app.risk_engine import RiskEngine, Risk, PresenceState
from app.alerts import AlertSystem

RISK_COLORS = {
    Risk.SAFE: (0, 200, 0),
    Risk.LOW: (0, 255, 255),
    Risk.MEDIUM: (0, 165, 255),
    Risk.HIGH: (0, 0, 255),
}


def setup_csv_logger():
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    path = os.path.join(config.LOGS_DIR, f"session_{time.strftime('%Y%m%d_%H%M%S')}.csv")
    f = open(path, "w", newline="")
    writer = csv.writer(f)
    writer.writerow(["timestamp", "risk", "score", "eye_closed", "closed_elapsed",
                      "blink_rate", "mouth_open", "total_yawns", "pitch_delta", "yaw_delta",
                      "phone", "drink", "food", "seatbelt_off", "messages"])
    return f, writer, path


def main():
    print("Starting DriverGuardian...")

    camera = Camera()
    presence_detector = PresenceDetector()
    face_mesh = FaceMeshWrapper()
    eye_tracker = EyeTracker()
    mouth_tracker = MouthTracker()
    drowsiness = DrowsinessDetector()
    head_pose_tracker = HeadPoseTracker()
    yolo = YoloDetector()
    yolo_confirmer = DetectionConfirmer()
    risk_engine = RiskEngine()
    alerts = AlertSystem()

    # Symmetric debounce: presence loss needs NO_FACE_GRACE_SEC to escalate
    # and PRESENCE_RECOVER_SEC of a confirmed face to clear. Obstruction
    # (covered lens / hand / object in front of camera) is checked
    # independently, with its own (shorter) confirm windows.
    presence_hysteresis = utils.Hysteresis(config.NO_FACE_GRACE_SEC, config.PRESENCE_RECOVER_SEC)
    obstruction_hysteresis = utils.Hysteresis(config.OBSTRUCTION_CONFIRM_SEC, config.OBSTRUCTION_RECOVER_SEC)

    log_file, csv_writer, log_path = setup_csv_logger()
    print(f"Logging session to: {log_path}")

    # ---- Calibration state ----
    calibrating = True
    calibration_start = None
    calib_ear, calib_mar, calib_pitch, calib_yaw = [], [], [], []

    prev_time = time.time()
    last_console_log = 0.0
    last_csv_log = 0.0
    frame_count = 0
    cached_yolo_state = {
        "phone": False, "drink": False, "food": False,
        "cigarette": None, "seatbelt_off": None, "raw_boxes": [],
    }

    print("Calibration will start once a face is detected.")
    print("Sit normally, look straight at the camera, eyes open.")

    try:
        while True:
            ret, frame = camera.read()
            if not ret:
                print("Camera read failed - stopping.")
                break

            h, w = frame.shape[:2]
            now = time.time()

            # Obstruction/brightness are measured on the RAW frame first -
            # CLAHE enhancement below would artificially inflate the local
            # contrast of a covered lens and defeat the obstruction check.
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            std_dev = utils.frame_std_dev(gray)
            brightness = utils.frame_mean_brightness(gray)
            if brightness < config.LOW_LIGHT_BRIGHTNESS_THRESHOLD:
                frame = utils.enhance_low_light(frame)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            landmarks, drawable = face_mesh.process(rgb_frame)
            face_found = landmarks is not None

            smoothed_ear, smoothed_mar, pitch, yaw = 0.30, 0.5, 0.0, 0.0
            if face_found:
                smoothed_ear = eye_tracker.update(landmarks, w, h)
                smoothed_mar = mouth_tracker.update(landmarks, w, h)
                p, y_, _ = estimate_pose(landmarks, w, h)
                if p is not None:
                    pitch, yaw = p, y_
                face_mesh.draw(frame, drawable)

            # ---- Calibration phase ----
            if calibrating:
                if face_found:
                    if calibration_start is None:
                        calibration_start = now
                    calib_ear.append(smoothed_ear)
                    calib_mar.append(smoothed_mar)
                    calib_pitch.append(pitch)
                    calib_yaw.append(yaw)
                    elapsed = now - calibration_start
                    cv2.putText(frame, f"CALIBRATING... look straight ahead, mouth closed ({elapsed:.1f}/{config.CALIBRATION_SEC:.0f}s)",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    if elapsed >= config.CALIBRATION_SEC:
                        baseline_ear = float(np.median(calib_ear))
                        baseline_mar = float(np.median(calib_mar))
                        baseline_pitch = float(np.median(calib_pitch))
                        baseline_yaw = float(np.median(calib_yaw))
                        drowsiness.set_baseline(baseline_ear)
                        drowsiness.set_mouth_baseline(baseline_mar)
                        head_pose_tracker.set_baseline(baseline_pitch, baseline_yaw)
                        calibrating = False
                        print(f"Calibration done. EAR={baseline_ear:.3f} MAR={baseline_mar:.3f} "
                              f"pitch={baseline_pitch:.1f} yaw={baseline_yaw:.1f}")
                else:
                    cv2.putText(frame, "Waiting for face to calibrate...",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                cv2.imshow("DriverGuardian", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            # ---- Presence classification (Phase 2 functional requirement) ----
            # Obstruction (covered lens, or a hand/object held in front of the
            # camera - both produce the same low-variance signature) and plain
            # absence (driver out of seat / turned fully away) are each
            # debounced symmetrically via Hysteresis: a single bad frame can't
            # fire an instant autonomous-stop, and a single lucky good frame
            # can't prematurely clear a real ongoing condition.
            presence_face = presence_detector.detect(rgb_frame)
            is_obstructed = obstruction_hysteresis.update(std_dev < config.FRAME_STD_BLOCKED_THRESHOLD, now)
            is_absent = presence_hysteresis.update(not face_found and not presence_face, now)

            if is_obstructed:
                presence = PresenceState.CAMERA_BLOCKED
            elif is_absent:
                presence = PresenceState.DRIVER_ABSENT
            else:
                presence = PresenceState.DRIVER_PRESENT

           # ---- Run detection pipelines ----
            pose_state = head_pose_tracker.update(pitch, yaw, now)
            drowsy_state = drowsiness.update(smoothed_ear, now, pose_state["pitch_delta"], smoothed_mar)

            frame_count += 1
            if frame_count % config.YOLO_INFER_EVERY_N_FRAMES == 0:
                roi = utils.mouth_roi(landmarks, w, h, config.MOUTH_PROXIMITY_RADIUS_MULT) if face_found else None
                raw_yolo_state = yolo.detect(frame, mouth_roi=roi)
                cached_yolo_state = yolo_confirmer.update(raw_yolo_state)
            yolo_state = cached_yolo_state

            risk, messages, debug = risk_engine.evaluate(
                now, presence, drowsy_state, pose_state, yolo_state
            )
            alerts.dispatch(risk, messages)

            # ---- Live overlay (updates every frame) ----
            color = RISK_COLORS[risk]
            cv2.putText(frame, f"RISK: {risk.name}  (score={debug.get('score', '-')})",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 3)

            panel = [
                f"Eyes: {'CLOSED' if drowsy_state['eye_closed'] else 'OPEN'}  "
                f"EAR={smoothed_ear:.2f} (thr<{drowsiness.closed_threshold:.2f})  "
                f"closed {drowsy_state['closed_elapsed']:.1f}s  level={drowsy_state['level'].name}"
                f"{'  [looking down - EAR suppressed]' if drowsy_state['looking_down'] else ''}",

                f"Head pitch: {pose_state['pitch_label']}  d={pose_state['pitch_delta']:+.1f} deg  "
                f"lean {pose_state['lean_elapsed']:.1f}s",

                f"Head yaw: {pose_state['yaw_label']} ({pose_state['yaw_zone']})  d={pose_state['yaw_delta']:+.1f} deg  "
                f"turn {pose_state['turn_elapsed']:.1f}s  risk={pose_state['turn_risk']}",

                f"Blinks/{config.BLINK_WINDOW_SEC:.0f}s: {drowsy_state['blink_rate']}  "
                f"Total: {drowsy_state['total_blinks']}",

                f"Mouth: {'OPEN' if drowsy_state['mouth_open'] else 'CLOSED'}  "
                f"MAR={smoothed_mar:.2f} (thr>{drowsiness.open_mouth_threshold:.2f})  "
                f"open {drowsy_state['open_elapsed']:.1f}s  "
                f"Yawns/{config.YAWN_RATE_WINDOW_SEC:.0f}s: {drowsy_state['yawn_rate']}  "
                f"Total: {drowsy_state['total_yawns']}"
                f"{'  [YAWNING]' if drowsy_state['is_yawning'] else ''}",

                f"YOLO: phone={yolo_state['phone']} drink={yolo_state['drink']} "
                f"food={yolo_state['food']} seatbelt_off={yolo_state['seatbelt_off']} "
                f"({'fine-tuned' if yolo.using_finetuned else 'pretrained' if yolo.available else 'disabled'})",

                f"Presence: {presence.name}  (std_dev={std_dev:.1f} brightness={brightness:.0f})",
            ]
            y = 58
            for line in panel:
                cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
                y += 19

            y += 8
            for m in messages[:4]:
                cv2.putText(frame, m, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
                y += 22

            curr_time = time.time()
            fps = 1.0 / (curr_time - prev_time) if curr_time != prev_time else 0.0
            prev_time = curr_time
            cv2.putText(frame, f"FPS: {fps:.1f}", (w - 120, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.putText(frame, "q=quit  r=recalibrate", (w - 260, h - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

            # ---- Console live log ----
            if now - last_console_log >= config.CONSOLE_LOG_INTERVAL_SEC:
                last_console_log = now
                print(f"[{utils.timestamp()}] RISK={risk.name:6s} score={debug.get('score')} | "
                      f"Eyes={'CLOSED' if drowsy_state['eye_closed'] else 'OPEN':6s} "
                      f"EAR={smoothed_ear:.2f} | Pitch={pose_state['pitch_label']:8s} "
                      f"d={pose_state['pitch_delta']:+5.1f} | Yaw={pose_state['yaw_label']:6s} "
                      f"d={pose_state['yaw_delta']:+5.1f} | {' / '.join(messages[:2])}")

            # ---- CSV log ----
            if now - last_csv_log >= config.CSV_LOG_INTERVAL_SEC:
                last_csv_log = now
                csv_writer.writerow([
                    utils.timestamp(), risk.name, debug.get("score"),
                    drowsy_state["eye_closed"], f"{drowsy_state['closed_elapsed']:.2f}",
                    drowsy_state["blink_rate"], drowsy_state["mouth_open"], drowsy_state["total_yawns"],
                    f"{pose_state['pitch_delta']:.1f}",
                    f"{pose_state['yaw_delta']:.1f}", yolo_state["phone"], yolo_state["drink"],
                    yolo_state["food"], yolo_state["seatbelt_off"], " / ".join(messages),
                ])
                log_file.flush()

            cv2.imshow("DriverGuardian", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                calibrating = True
                calibration_start = None
                calib_ear.clear()
                calib_mar.clear()
                calib_pitch.clear()
                calib_yaw.clear()
                eye_tracker.reset()
                mouth_tracker.reset()
                drowsiness.reset()
                presence_hysteresis.reset()
                obstruction_hysteresis.reset()

    finally:
        camera.release()
        cv2.destroyAllWindows()
        presence_detector.close()
        face_mesh.close()
        log_file.close()
        print(f"Session log saved: {log_path}")


if __name__ == "__main__":
    main()

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

# Reserve one CPU core exclusively for the desktop compositor/window
# manager, enforced at the OS scheduling level - not a request to any
# individual library. Capping YOLO's own thread pool (torch/ncnn) helped
# but didn't fully stop the screen freezing on the Pi, because MediaPipe's
# TFLite delegate can't be thread-capped through its public Python API
# (checked directly: BaseOptions only exposes a CPU/GPU delegate choice,
# no num_threads) and runs on every single frame, not just every-Nth like
# YOLO. CPU affinity sidesteps needing every library to cooperate: no
# thread of this process, no matter which library spawned it, can ever be
# scheduled onto a reserved core. Set before importing anything that
# spins up its own thread pool (mediapipe/torch/ncnn below), though the
# OS enforces this for the process's whole lifetime regardless of import
# order. No-ops on Windows (sched_setaffinity is Linux-only) and on a
# dev/CI machine with 2 or fewer cores, where reserving one wouldn't
# leave enough for the app itself.
if hasattr(os, "sched_setaffinity"):
    _all_cpus = os.sched_getaffinity(0)
    if len(_all_cpus) > 2:
        _reserved_cpu = max(_all_cpus)
        os.sched_setaffinity(0, _all_cpus - {_reserved_cpu})
        print(f"[main] Reserved CPU core {_reserved_cpu} for the desktop session "
              f"(app restricted to {sorted(_all_cpus - {_reserved_cpu})})")

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
    writer.writerow(["timestamp", "risk", "case", "score", "eye_closed", "closed_elapsed",
                      "blink_rate", "mouth_open", "total_yawns", "pitch_delta", "yaw_delta",
                      "phone", "consumption", "seatbelt_off", "messages"])
    return f, writer, path


def main():
    print("Starting DriverGuardian...")

    # Reverted WINDOW_NORMAL: scaling the frame to fill a resized/maximized
    # window costs a real resize on every single imshow() call, which on
    # the Pi's CPU was a steady per-frame tax contributing to the FPS drop.
    # Back to imshow()'s default AUTOSIZE (1:1 blit, no scaling) - the
    # window pins at the frame's native size instead of filling whatever
    # size it's resized to.

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
        "phone": False, "consumption": False,
        "cigarette": None, "seatbelt_off": None, "raw_boxes": [],
    }

    # ---- Per-stage profiling (diagnostic: which stage actually owns the
    # frame budget). Accumulated and averaged over PROFILE_LOG_INTERVAL_SEC
    # rather than printed every frame - printing itself isn't free and
    # would skew the very thing being measured.
    stage_totals = {"camera": 0.0, "preprocess": 0.0, "mediapipe": 0.0,
                     "presence_logic": 0.0, "yolo": 0.0, "risk_draw": 0.0,
                     "display": 0.0}
    profile_frames = 0
    last_profile_log = 0.0

    print("Calibration will start once a face is detected.")
    print("Sit normally, look straight at the camera, eyes open.")

    try:
        while True:
            t_loop_start = time.perf_counter()
            ret, frame = camera.read()
            if not ret:
                print("Camera read failed - stopping.")
                break
            t_camera = time.perf_counter()

            h, w = frame.shape[:2]
            now = time.time()

            # Obstruction/brightness are measured on the RAW frame first -
            # CLAHE enhancement below would artificially inflate the local
            # contrast of a covered lens and defeat the obstruction check.
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            std_dev = utils.frame_std_dev(gray)
            brightness = utils.frame_mean_brightness(gray)
            # NOTE: CLAHE-enhanced frames also get fed to YOLO (not just
            # MediaPipe) - a prior attempt to hold back the raw frame from
            # YOLO here (on the untested theory that CLAHE hurt it, since
            # the model never saw enhanced images during training) turned
            # out to measurably hurt phone detection in practice. Reverted:
            # real-world results over an unproven theory.
            if brightness < config.LOW_LIGHT_BRIGHTNESS_THRESHOLD:
                frame = utils.enhance_low_light(frame)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            t_preprocess = time.perf_counter()

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
            t_mediapipe = time.perf_counter()

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
            # presence_detector only matters when face_found is already
            # False (see is_absent below - `and` short-circuits on it
            # otherwise) - only actually run it then instead of eagerly
            # every frame, since it's a full BlazeFace inference (~5.5ms)
            # that's pure waste in the common case (driver present, main
            # landmarker already found a face).
            presence_face = presence_detector.detect(rgb_frame) if not face_found else False
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
            t_presence_logic = time.perf_counter()

            frame_count += 1
            if frame_count % config.YOLO_INFER_EVERY_N_FRAMES == 0:
                roi = utils.mouth_roi(landmarks, w, h, config.MOUTH_PROXIMITY_RADIUS_MULT) if face_found else None
                raw_yolo_state = yolo.detect(frame, mouth_roi=roi)
                cached_yolo_state = yolo_confirmer.update(raw_yolo_state, now)
            yolo_state = cached_yolo_state
            t_yolo = time.perf_counter()

            # ---- Draw YOLO bounding boxes ----
            # Green = this box cleared its confidence/mouth-proximity gate
            # and actually fed a phone/drink/etc. flag below. Yellow = the
            # model drew it, but it never counted for anything (too low
            # confidence, or - for drink/food/cigarette - not near the
            # mouth). Distinguishing these on-screen matters: a box that's
            # merely visible is not the same as one that actually triggered
            # a warning, and conflating them makes false-positive/negative
            # reports hard to diagnose.
            for x1, y1, x2, y2, label, conf, counted in yolo_state["raw_boxes"]:
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                box_color = (0, 255, 0) if counted else (255, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                cv2.putText(frame, f"{label} {conf:.2f}{'*' if counted else ''}", (x1, max(y1 - 8, 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)

            risk, messages, debug = risk_engine.evaluate(
                now, presence, drowsy_state, pose_state, yolo_state
            )
            alerts.dispatch(risk, messages, debug.get("case", "NONE"))

            # ---- Live overlay (updates every frame) ----
            color = RISK_COLORS[risk]
            cv2.putText(frame, f"RISK: {risk.name}  case={debug.get('case', 'NONE')}  (score={debug.get('score', '-')})",
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

                f"YOLO: phone={yolo_state['phone']} consumption={yolo_state['consumption']} "
                f"cigarette={yolo_state['cigarette']} "
                f"SEATBELT: {utils.seatbelt_label(yolo_state['seatbelt_off'])} "
                f"({'fine-tuned' if yolo.using_finetuned else 'pretrained' if yolo.available else 'disabled'})",

                # Raw model output (label:confidence, '*' = cleared its gate
                # and counted toward the flags above) - diagnostic visibility
                # into what the model actually sees, before K-of-N
                # confirmation is applied on top.
                "Raw boxes: " + (", ".join(f"{lbl}:{conf:.2f}{'*' if counted else ''}"
                                            for *_, lbl, conf, counted in yolo_state["raw_boxes"])
                                  or "(none)"),

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
                print(f"[{utils.timestamp()}] RISK={risk.name:6s} case={debug.get('case', 'NONE'):16s} score={debug.get('score')} | "
                      f"Eyes={'CLOSED' if drowsy_state['eye_closed'] else 'OPEN':6s} "
                      f"EAR={smoothed_ear:.2f} | Pitch={pose_state['pitch_label']:8s} "
                      f"d={pose_state['pitch_delta']:+5.1f} | Yaw={pose_state['yaw_label']:6s} "
                      f"d={pose_state['yaw_delta']:+5.1f} | {' / '.join(messages[:2])}")
                if yolo_state["raw_boxes"]:
                    boxes_str = ", ".join(f"{lbl}:{conf:.2f}{'*' if counted else ''}"
                                           for *_, lbl, conf, counted in yolo_state["raw_boxes"])
                    print(f"    -> YOLO raw: {boxes_str}")

            # ---- CSV log ----
            if now - last_csv_log >= config.CSV_LOG_INTERVAL_SEC:
                last_csv_log = now
                csv_writer.writerow([
                    utils.timestamp(), risk.name, debug.get("case", "NONE"), debug.get("score"),
                    drowsy_state["eye_closed"], f"{drowsy_state['closed_elapsed']:.2f}",
                    drowsy_state["blink_rate"], drowsy_state["mouth_open"], drowsy_state["total_yawns"],
                    f"{pose_state['pitch_delta']:.1f}",
                    f"{pose_state['yaw_delta']:.1f}", yolo_state["phone"],
                    yolo_state["consumption"], yolo_state["seatbelt_off"], " / ".join(messages),
                ])
                log_file.flush()

            t_risk_draw = time.perf_counter()
            cv2.imshow("DriverGuardian", frame)
            key = cv2.waitKey(1) & 0xFF
            t_display = time.perf_counter()

            stage_totals["camera"] += t_camera - t_loop_start
            stage_totals["preprocess"] += t_preprocess - t_camera
            stage_totals["mediapipe"] += t_mediapipe - t_preprocess
            stage_totals["presence_logic"] += t_presence_logic - t_mediapipe
            stage_totals["yolo"] += t_yolo - t_presence_logic
            stage_totals["risk_draw"] += t_risk_draw - t_yolo
            stage_totals["display"] += t_display - t_risk_draw
            profile_frames += 1

            if now - last_profile_log >= config.PROFILE_LOG_INTERVAL_SEC and profile_frames > 0:
                last_profile_log = now
                total = sum(stage_totals.values())
                avg_fps = profile_frames / total if total > 0 else 0.0
                breakdown = " ".join(f"{k}={(v / profile_frames) * 1000:.1f}ms"
                                      for k, v in stage_totals.items())
                print(f"[PROFILE] avg_fps={avg_fps:.1f} over {profile_frames} frames | {breakdown}")
                stage_totals = {k: 0.0 for k in stage_totals}
                profile_frames = 0

                # Printed on the same cadence as [PROFILE] so a temp/
                # throttle reading always lines up with the FPS numbers
                # next to it - sudden intermittent drops are a classic
                # symptom of thermal throttling or under-voltage, and no
                # software fix elsewhere in this app can solve that.
                thermal = utils.check_pi_thermal_status()
                if thermal["available"]:
                    if thermal["flags"]:
                        print(f"[THERMAL] temp={thermal['temp_c']:.1f}C  "
                              f"THROTTLING DETECTED: {', '.join(thermal['flags'])} "
                              f"- this needs a hardware fix (PSU/heatsink/fan), "
                              f"not a software one")
                    else:
                        print(f"[THERMAL] temp={thermal['temp_c']:.1f}C  no throttling")

                # Same cadence, same reasoning: a process blocked swapping
                # in from a slow SD card doesn't need a CPU core, so it's
                # invisible to CPU-affinity/thread-cap fixes but produces
                # the exact same "everything freezes, then catches up"
                # symptom - rule it in/out directly instead of guessing.
                mem = utils.check_memory_status()
                if mem["available"]:
                    swap_note = (f"SWAPPING {mem['swap_used_mb']:.0f}/{mem['swap_total_mb']:.0f}MB"
                                 if mem["swap_used_mb"] > 1.0 else "no swap use")
                    print(f"[MEMORY] used={mem['mem_used_pct']:.0f}% "
                          f"available={mem['mem_available_mb']:.0f}MB  {swap_note}")

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
        alerts.close()
        log_file.close()
        print(f"Session log saved: {log_path}")


if __name__ == "__main__":
    main()

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

# ---- Keep the rest of the Pi responsive while this app runs ----
# Everything in this block must run BEFORE numpy/cv2/mediapipe/ncnn are
# imported: thread-pool sizes are read from the environment once at library
# load, and CPU priority/affinity are inherited by every thread created
# afterwards - so every library thread ends up covered, not just ours.
#
# 1. OpenMP (NCNN's YOLO threads) sleeps between inferences instead of
#    busy-spinning on the CPU, and BLAS pools stay single-threaded.
_APP_THREADS = str(max(1, (os.cpu_count() or 4) - 2))
os.environ.setdefault("OMP_NUM_THREADS", _APP_THREADS)
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from app import config  # noqa: E402  (config only imports os)

# 2. Lower CPU priority. Pinning to fewer cores (below) still leaves this
#    app competing on equal terms with the desktop compositor, audio
#    (PipeWire, Bluetooth speaker) and bluetoothd on every core it uses -
#    and memory bandwidth and heat are shared across all cores anyway. At a
#    lower priority the kernel always serves those first; the app only
#    loses time when the system genuinely needs it, so monitoring FPS is
#    unaffected on an otherwise idle Pi.
if config.APP_NICE and hasattr(os, "nice"):
    try:
        os.nice(config.APP_NICE)
        print(f"[main] Running at lower CPU priority (nice +{config.APP_NICE}) "
              f"so the desktop, audio and Bluetooth stay responsive")
    except OSError as e:
        print(f"[main] Could not lower CPU priority: {e}")

# 3. Reserve one CPU core exclusively for the desktop compositor/window
# manager, enforced at the OS scheduling level - not a request to any
# individual library. Capping YOLO's own thread pool (torch/ncnn) helped
# but didn't fully stop the screen freezing on the Pi, because MediaPipe's
# TFLite delegate can't be thread-capped through its public Python API
# (checked directly: BaseOptions only exposes a CPU/GPU delegate choice,
# no num_threads) and runs on every single frame, not just every-Nth like
# YOLO. CPU affinity sidesteps needing every library to cooperate: no
# thread of this process, no matter which library spawned it, can ever be
# scheduled onto a reserved core. No-ops on macOS/Windows
# (sched_setaffinity is Linux-only) and on a machine with 2 or fewer
# cores, where reserving one wouldn't leave enough for the app itself.
if hasattr(os, "sched_setaffinity"):
    _all_cpus = os.sched_getaffinity(0)
    if len(_all_cpus) > 2:
        _reserved_cpu = max(_all_cpus)
        os.sched_setaffinity(0, _all_cpus - {_reserved_cpu})
        print(f"[main] Reserved CPU core {_reserved_cpu} for the desktop session "
              f"(app restricted to {sorted(_all_cpus - {_reserved_cpu})})")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

# OpenCV's own worker pool: the per-frame colour conversions/CLAHE are
# small, and a pool the size of the whole CPU just adds wake-ups and
# contention with MediaPipe and YOLO for no real speed-up.
cv2.setNumThreads(2)

from app import utils  # noqa: E402
from app.camera import Camera
from app.face_detector import PresenceDetector
from app.face_mesh import FaceMeshWrapper
from app.eye_tracker import EyeTracker
from app.mouth_tracker import MouthTracker
from app.drowsiness import DrowsinessDetector
from app.head_pose import estimate_pose, HeadPoseTracker
from app.yolo_detector import YoloProcess
from app.risk_engine import RiskEngine, Risk, PresenceState
from app.alerts import AlertSystem
from app.web_view import WebView

RISK_COLORS = {
    Risk.WAITING: (200, 200, 200),
    Risk.SAFE: (0, 200, 0),
    Risk.LOW: (0, 255, 255),
    Risk.MEDIUM: (0, 165, 255),
    Risk.HIGH: (0, 0, 255),
}


def _r(x, nd=3):
    return None if x is None else round(float(x), nd)


def dashboard_state(*, risk, debug, messages, presence, face_found, drowsy_state, drowsiness,
                    ear, mar, pose_state, yolo_state, yolo, std_dev, brightness,
                    perf, thermal, sysinfo, links, baseline, calibrating=False, calib_progress=None):
    """Everything the web dashboard shows, as plain JSON-able values."""
    seatbelt_off = yolo_state.get("seatbelt_off")
    return {
        "risk": risk.name, "case": debug.get("case", "NONE"), "score": debug.get("score"),
        "messages": list(messages[:4]), "presence": presence.name if presence else None,
        "face_found": face_found, "calibrating": calibrating, "calib_progress": calib_progress,
        "baseline": baseline,
        "eyes": None if drowsy_state is None else {
            "closed": drowsy_state["eye_closed"], "ear": _r(ear), "ear_thr": _r(drowsiness.closed_threshold),
            "closed_sec": _r(drowsy_state["closed_elapsed"], 2), "blink_rate": drowsy_state["blink_rate"],
            "blink_window_sec": config.BLINK_WINDOW_SEC, "blinks_total": drowsy_state["total_blinks"],
            "level": drowsy_state["level"].name, "looking_down": drowsy_state["looking_down"],
        },
        "mouth": None if drowsy_state is None else {
            "open": drowsy_state["mouth_open"], "mar": _r(mar), "mar_thr": _r(drowsiness.open_mouth_threshold),
            "open_sec": _r(drowsy_state["open_elapsed"], 2), "yawning": drowsy_state["is_yawning"],
            "yawns_window": drowsy_state["yawn_rate"], "yawns_total": drowsy_state["total_yawns"],
        },
        "head": None if pose_state is None else {
            "pitch": _r(pose_state["pitch_delta"], 1), "yaw": _r(pose_state["yaw_delta"], 1),
            "pitch_label": pose_state["pitch_label"], "yaw_label": pose_state["yaw_label"],
            "yaw_zone": pose_state["yaw_zone"], "turn_sec": _r(pose_state["turn_elapsed"], 1),
            "lean_sec": _r(pose_state["lean_elapsed"], 1), "turn_risk": pose_state["turn_risk"],
        },
        "objects": {
            "phone": yolo_state.get("phone"), "consumption": yolo_state.get("consumption"),
            "cigarette": yolo_state.get("cigarette"),
            "seatbelt": utils.seatbelt_label(seatbelt_off) if yolo.using_finetuned else "N/A",
            "boxes": [{"label": b[4], "conf": _r(b[5], 2), "counted": b[6]} for b in yolo_state.get("raw_boxes", [])],
        },
        "camera": {"brightness": _r(brightness, 0), "std_dev": _r(std_dev, 1),
                   "low_light": brightness is not None and brightness < config.LOW_LIGHT_BRIGHTNESS_THRESHOLD},
        "perf": perf,
        "system": None if not thermal and not sysinfo else {
            "temp_c": _r(thermal.get("temp_c"), 1) if thermal else None,
            "throttled": thermal.get("flags", []) if thermal else [],
            **({k: _r(v, 2) for k, v in sysinfo.items()} if sysinfo else {}),
        },
        "links": links,
        "requirements": {"min_avg_rate_hz": config.RISK_UPDATE_MIN_AVG_HZ,
                         "max_gap_ms": 1000.0 / config.RISK_UPDATE_MIN_HZ},
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
    yolo = YoloProcess()   # own process - see yolo_detector.YoloProcess
    risk_engine = RiskEngine()
    alerts = AlertSystem()
    web = WebView()   # live view in a browser - see app/web_view.py

    # Symmetric debounce: presence loss needs NO_FACE_GRACE_SEC to escalate
    # and PRESENCE_RECOVER_SEC of a confirmed face to clear. Obstruction
    # (covered lens / hand / object in front of camera) is checked
    # independently, with its own (shorter) confirm windows.
    presence_hysteresis = utils.Hysteresis(config.NO_FACE_GRACE_SEC, config.PRESENCE_RECOVER_SEC)
    obstruction_hysteresis = utils.Hysteresis(config.OBSTRUCTION_CONFIRM_SEC, config.OBSTRUCTION_RECOVER_SEC)

    log_file, csv_writer, log_path = setup_csv_logger()
    print(f"Logging session to: {log_path}")

    # Optional per-classification timestamp log (requirement evidence; see
    # config.RISK_UPDATE_LOG and tools/check_update_rate.py).
    risk_log_file = risk_log_writer = None
    if config.RISK_UPDATE_LOG:
        risk_log_path = log_path.replace("session_", "risk_updates_")
        risk_log_file = open(risk_log_path, "w", newline="")
        risk_log_writer = csv.writer(risk_log_file)
        risk_log_writer.writerow(["t_monotonic", "risk", "case", "segment"])
        print(f"Logging every risk classification to: {risk_log_path}")

    # ---- Calibration state ----
    calibrating = True
    calibration_start = None
    calib_ear, calib_mar, calib_pitch, calib_yaw = [], [], [], []

    prev_time = time.monotonic()
    fps_display = 0.0   # smoothed FPS for the dashboard
    # Latest values from the [PROFILE] cadence, for the dashboard
    last_stages, last_rate_hz, last_gap_window_ms = {}, None, None
    last_thermal, last_sysinfo = None, None
    calib_baseline = None   # calibrated values, for the dashboard
    last_console_log = 0.0
    last_csv_log = 0.0
    last_yolo_submit = 0.0
    frame_count = 0

    # ---- Per-stage profiling (diagnostic: which stage actually owns the
    # frame budget). Accumulated and averaged over PROFILE_LOG_INTERVAL_SEC
    # rather than printed every frame - printing itself isn't free and
    # would skew the very thing being measured.
    stage_totals = {"camera": 0.0, "preprocess": 0.0, "mediapipe": 0.0,
                     "presence_logic": 0.0, "yolo": 0.0, "risk_draw": 0.0,
                     "imshow": 0.0, "waitkey": 0.0}
    profile_frames = 0
    last_profile_log = 0.0
    # Rolling baseline for the per-frame [STUTTER] outlier check below,
    # plus per-window accumulators so outliers are summarised once per
    # [PROFILE] rather than printed one line each.
    frame_time_history = deque(maxlen=config.STUTTER_WINDOW_FRAMES)
    stutter_count = 0
    stutter_worst = None  # (frame_total, baseline, stage_str) of the worst so far

    # ---- Risk classification update rate (requirement: >= 0.2 Hz, i.e. a
    # new Low/Medium/High classification at least every 5 s). Measured on
    # time.monotonic() - the Pi's wall clock can jump when NTP syncs, which
    # would fake a huge gap (or a negative one). WAITING (pre-drive /
    # calibration) is not a risk classification, so the gap clock is reset
    # there and only starts once real monitoring is running.
    risk_max_gap = 1.0 / config.RISK_UPDATE_MIN_HZ
    risk_updates = 0
    risk_last_t = None
    risk_window_start = time.monotonic()
    risk_segment = 0   # increments each time classification (re)starts after WAITING
    risk_gap_window_max = 0.0
    risk_gap_session_max = 0.0

    print("Calibration will start once a face is detected.")
    print("Sit normally, look straight at the camera, eyes open.")

    try:
        while True:
            t_loop_start = time.perf_counter()
            frame_count += 1
            # The preview window only updates every DISPLAY_EVERY_N_FRAMES
            # (waitKey() blocks on the compositor, ~24 ms measured on the Pi).
            display_due = config.DISPLAY_ENABLED and frame_count % config.DISPLAY_EVERY_N_FRAMES == 0
            ret, frame = camera.read()
            if not ret:
                print("Camera read failed - stopping.")
                break
            t_camera = time.perf_counter()

            h, w = frame.shape[:2]
            # Monotonic, never wall-clock: every timer in the app (eye
            # closure, head turn/lean, seatbelt, presence debounce) measures
            # durations from this. The Pi's wall clock jumps when it syncs
            # over the network after boot - hours forward on a Pi without a
            # clock battery - which would make any timer running at that
            # moment read "hours elapsed" and fire a false HIGH alert.
            now = time.monotonic()
            # Overlays are only drawn on frames someone will actually see -
            # the local window and/or a browser watching the live view.
            stream_due = web.wants_frame(now)
            show = display_due or stream_due

            # Obstruction/brightness are measured on the RAW frame first -
            # CLAHE enhancement below would artificially inflate the local
            # contrast of a covered lens and defeat the obstruction check.
            # Measured on a 1/4-scale copy: mean/std-dev of a
            # nearest-neighbour downsample match the full frame's, at ~1/16
            # of the per-frame cost (np.std on the full 1280x720 frame
            # converts ~0.9M pixels to float64 every frame).
            gray = cv2.cvtColor(cv2.resize(frame, (w // 4, h // 4), interpolation=cv2.INTER_NEAREST),
                                cv2.COLOR_BGR2GRAY)
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
                    if show:
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
                        calib_baseline = {"ear": baseline_ear, "mar": baseline_mar,
                                    "pitch": baseline_pitch, "yaw": baseline_yaw}
                        print(f"Calibration done. EAR={baseline_ear:.3f} MAR={baseline_mar:.3f} "
                              f"pitch={baseline_pitch:.1f} yaw={baseline_yaw:.1f}")
                elif show:
                    cv2.putText(frame, "Waiting for face to calibrate...",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                # Keep the ESP32 fed during calibration too - it's the same
                # "not monitoring yet" phase as the pre-drive check, and a
                # silent Pi would trip the ESP32's link-loss watchdog into a
                # full HIGH alarm (see Risk.WAITING).
                alerts.dispatch(Risk.WAITING, ["Calibrating"], "CALIBRATING")
                risk_last_t = None  # not classifying yet - see risk-rate block
                if web.wants_status(now):
                    health = alerts.health(now)
                    web.set_status(dashboard_state(
                        risk=Risk.WAITING, debug={"case": "CALIBRATING"},
                        messages=["Calibrating - look straight at the camera"],
                        presence=None, face_found=face_found, drowsy_state=None, drowsiness=drowsiness,
                        ear=smoothed_ear, mar=smoothed_mar, pose_state=None,
                        yolo_state=yolo.get_latest(), yolo=yolo, std_dev=std_dev, brightness=brightness,
                        perf={"fps": _r(fps_display, 1), "stages_ms": last_stages},
                        thermal=last_thermal, sysinfo=last_sysinfo,
                        links={**health, "yolo": yolo.health(now)["state"]}, baseline=calib_baseline,
                        calibrating=True,
                        calib_progress=(min(1.0, (now - calibration_start) / config.CALIBRATION_SEC)
                                        if calibration_start is not None else 0.0)), now)

                if show and face_found:
                    face_mesh.draw(frame, drawable)
                if stream_due:
                    web.publish(frame, now)
                if display_due:
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
            pose_state = head_pose_tracker.update(pitch, yaw, now, face_found=face_found)
            drowsy_state = drowsiness.update(smoothed_ear, now, pose_state["pitch_delta"],
                                             smoothed_mar, face_found=face_found)
            t_presence_logic = time.perf_counter()

            # YOLO gets the frame BEFORE anything is drawn on it - the face
            # mesh dots used to be drawn first, so YOLO was looking at 478
            # green dots painted over the face and mouth, exactly where it
            # looks for phones, drinks and cigarettes.
            if time.monotonic() - last_yolo_submit >= config.YOLO_INTERVAL_SEC:
                roi = utils.mouth_roi(landmarks, w, h, config.MOUTH_PROXIMITY_RADIUS_MULT) if face_found else None
                if yolo.submit(frame, roi):
                    last_yolo_submit = time.monotonic()
            yolo_state = yolo.get_latest()
            if show and face_found:
                face_mesh.draw(frame, drawable)
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
            if show:
                for x1, y1, x2, y2, label, conf, counted in yolo_state["raw_boxes"]:
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    box_color = (0, 255, 0) if counted else (255, 255, 0)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                    cv2.putText(frame, f"{label} {conf:.2f}{'*' if counted else ''}", (x1, max(y1 - 8, 12)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)

            # seatbelt_supported: the pre-drive gate can only demand a
            # confirmed belt when the loaded model actually has that class -
            # the COCO-pretrained fallback does not (see yolo_detector).
            risk, messages, debug = risk_engine.evaluate(
                now, presence, drowsy_state, pose_state, yolo_state,
                seatbelt_supported=yolo.using_finetuned,
            )
            alerts.dispatch(risk, messages, debug.get("case", "NONE"))

            if web.wants_status(now):
                health = alerts.health(now)
                yh = yolo.health(now)
                web.set_status(dashboard_state(
                    risk=risk, debug=debug, messages=messages, presence=presence, face_found=face_found,
                    drowsy_state=drowsy_state, drowsiness=drowsiness, ear=smoothed_ear, mar=smoothed_mar,
                    pose_state=pose_state, yolo_state=yolo_state, yolo=yolo,
                    std_dev=std_dev, brightness=brightness,
                    perf={"fps": _r(fps_display, 1), "stages_ms": last_stages,
                          "rate_hz": last_rate_hz, "gap_window_ms": last_gap_window_ms,
                          "gap_session_ms": _r(risk_gap_session_max * 1000, 0),
                          "camera_fps": config.CAMERA_FPS},
                    thermal=last_thermal, sysinfo=last_sysinfo,
                    links={**health, "yolo": yh["state"], "yolo_age": _r(yh["result_age"], 1)},
                    baseline=calib_baseline), now)

            if risk == Risk.WAITING:
                risk_last_t = None
            else:
                t_class = time.monotonic()
                if risk_last_t is None:
                    risk_segment += 1
                if risk_last_t is not None:
                    gap = t_class - risk_last_t
                    risk_gap_window_max = max(risk_gap_window_max, gap)
                    risk_gap_session_max = max(risk_gap_session_max, gap)
                risk_last_t = t_class
                risk_updates += 1
                if risk_log_writer is not None:
                    risk_log_writer.writerow([f"{t_class:.6f}", risk.name,
                                              debug.get("case", "NONE"), risk_segment])

            # ---- Live overlay (updates every frame) ----
            color = RISK_COLORS[risk]
            if display_due:
                cv2.putText(frame, f"RISK: {risk.name}  case={debug.get('case', 'NONE')}  (score={debug.get('score', '-')})",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 3)

            # The detailed text panel is only for the local window - the web
            # dashboard shows the same values as proper UI next to the video.
            if display_due:
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

            curr_time = time.monotonic()
            fps = 1.0 / (curr_time - prev_time) if curr_time != prev_time else 0.0
            prev_time = curr_time
            fps_display = fps if not fps_display else 0.9 * fps_display + 0.1 * fps
            if display_due:
                cv2.putText(frame, f"FPS: {fps:.1f}", (w - 120, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                cv2.putText(frame, "q=quit  r=recalibrate", (w - 260, h - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

            # ---- Console live log ----
            if config.CONSOLE_LOG_ENABLED and now - last_console_log >= config.CONSOLE_LOG_INTERVAL_SEC:
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
            if stream_due:
                web.publish(frame, now)
            if display_due:
                # Preview-only downscale - see config.DISPLAY_SCALE.
                # Everything downstream of detection already ran on the
                # full-resolution frame, so this costs no accuracy; it
                # only shrinks what the (software, no-OpenGL) Qt
                # renderer has to blit inside waitKey() below.
                if config.DISPLAY_SCALE != 1.0:
                    preview = cv2.resize(frame, None, fx=config.DISPLAY_SCALE,
                                         fy=config.DISPLAY_SCALE,
                                         interpolation=cv2.INTER_NEAREST)
                else:
                    preview = frame
                cv2.imshow("DriverGuardian", preview)
                # imshow() and waitKey() timed separately: the combined
                # "display" stage was confirmed to spike to ~100ms roughly
                # once a second (see [STUTTER]), but they fail for very
                # different reasons - imshow() blocking points at frame
                # data volume through this Qt build's software renderer (no
                # OpenGL support), while waitKey() blocking points at the
                # GUI event loop / compositor sync instead. waitKey() used
                # to run on every frame even when nothing new was shown,
                # which is why DISPLAY_EVERY_N_FRAMES alone changed nothing
                # earlier - both now only run on shown frames.
                t_imshow = time.perf_counter()
                key = cv2.waitKey(1) & 0xFF
            elif config.DISPLAY_ENABLED:
                # Frame not shown: skip the GUI entirely. Key presses queue up
                # in the window and are read on the next shown frame.
                key = 0xFF
                t_imshow = time.perf_counter()
            else:
                # No window, no keyboard input possible - quit via Ctrl+C
                # (already works, propagates as KeyboardInterrupt through
                # the `finally` cleanup block below) and recalibration only
                # happens once at startup, not re-triggerable mid-session.
                key = 0xFF
                t_imshow = time.perf_counter()
            t_display = time.perf_counter()

            frame_stages = {
                "camera": t_camera - t_loop_start,
                "preprocess": t_preprocess - t_camera,
                "mediapipe": t_mediapipe - t_preprocess,
                "presence_logic": t_presence_logic - t_mediapipe,
                "yolo": t_yolo - t_presence_logic,
                "risk_draw": t_risk_draw - t_yolo,
                "imshow": t_imshow - t_risk_draw,
                "waitkey": t_display - t_imshow,
            }
            frame_total = sum(frame_stages.values())

            # Per-frame outlier detector: [PROFILE] only reports 5-second
            # averages, which can't show which single frame actually
            # stalled or by how much - exactly the gap that made the
            # earlier "flickering"/stutter report hard to pin down (YOLO's
            # own average dropped to ~0ms after threading it, but the
            # stutter itself was still reported as present). Compares each
            # frame's total time against a rolling baseline of the last
            # STUTTER_WINDOW_FRAMES frames (excluding itself) and flags
            # anything that's a clear multiple of that baseline, with a
            # per-stage breakdown for that exact frame - so instead of
            # guessing candidates one at a time, this shows directly which
            # stage caused the spike and how often it happens.
            # Accumulated rather than printed per-occurrence: at one line
            # per outlier this floods the console (and printing is itself
            # slow enough to perturb the very timing being measured). One
            # summary per [PROFILE] window is also strictly more useful -
            # it gives the frequency, not just isolated events.
            if len(frame_time_history) >= config.STUTTER_MIN_SAMPLES:
                baseline = sum(frame_time_history) / len(frame_time_history)
                if frame_total >= baseline * config.STUTTER_MULTIPLIER:
                    stutter_count += 1
                    if stutter_worst is None or frame_total > stutter_worst[0]:
                        stage_str = " ".join(f"{k}={v * 1000:.1f}ms"
                                              for k, v in frame_stages.items())
                        stutter_worst = (frame_total, baseline, stage_str)
            frame_time_history.append(frame_total)

            for _stage, _elapsed in frame_stages.items():
                stage_totals[_stage] += _elapsed
            profile_frames += 1

            if now - last_profile_log >= config.PROFILE_LOG_INTERVAL_SEC and profile_frames > 0:
                last_profile_log = now
                total = sum(stage_totals.values())
                avg_fps = profile_frames / total if total > 0 else 0.0
                breakdown = " ".join(f"{k}={(v / profile_frames) * 1000:.1f}ms"
                                      for k, v in stage_totals.items())
                print(f"[PROFILE] avg_fps={avg_fps:.1f} over {profile_frames} frames | {breakdown}")
                last_stages = {k: round(v / profile_frames * 1000, 1) for k, v in stage_totals.items()}
                if stutter_count:
                    worst_total, worst_baseline, worst_stages = stutter_worst
                    print(f"[STUTTER] {stutter_count} of {profile_frames} frames "
                          f">{config.STUTTER_MULTIPLIER:g}x baseline | worst "
                          f"{worst_total * 1000:.1f}ms vs ~{worst_baseline * 1000:.1f}ms "
                          f"| {worst_stages}")
                stutter_count = 0
                stutter_worst = None

                t_window = time.monotonic()
                if risk_updates:
                    rate = risk_updates / (t_window - risk_window_start)
                    last_rate_hz, last_gap_window_ms = round(rate, 1), round(risk_gap_window_max * 1000)
                    verdict = "PASS" if risk_gap_session_max <= risk_max_gap else "FAIL"
                    print(f"[RISK-RATE] {rate:.1f} Hz over {risk_updates} classifications "
                          f"| longest gap {risk_gap_window_max * 1000:.0f}ms "
                          f"| session longest {risk_gap_session_max * 1000:.0f}ms "
                          f"| req >= {config.RISK_UPDATE_MIN_HZ:g} Hz "
                          f"(gap <= {risk_max_gap * 1000:.0f}ms): {verdict}")
                else:
                    print("[RISK-RATE] no classifications this window (waiting/calibrating)")
                risk_updates = 0
                risk_gap_window_max = 0.0
                risk_window_start = t_window
                stage_totals = {k: 0.0 for k in stage_totals}
                profile_frames = 0

                # Printed on the same cadence as [PROFILE] so a temp/
                # throttle reading always lines up with the FPS numbers
                # next to it - sudden intermittent drops are a classic
                # symptom of thermal throttling or under-voltage, and no
                # software fix elsewhere in this app can solve that.
                thermal = utils.check_pi_thermal_status()
                last_thermal = thermal if thermal["available"] else None
                if thermal["available"]:
                    if thermal["flags"]:
                        print(f"[THERMAL] temp={thermal['temp_c']:.1f}C  "
                              f"THROTTLING DETECTED: {', '.join(thermal['flags'])} "
                              f"- this needs a hardware fix (PSU/heatsink/fan), "
                              f"not a software one")
                    else:
                        print(f"[THERMAL] temp={thermal['temp_c']:.1f}C  no throttling")

                # Whole-system picture on the same cadence: if the desktop
                # lags while FPS looks fine, this shows whether the Pi is
                # out of CPU (load), out of RAM (swapping to the SD card
                # stalls everything, not just this app) or leaking threads.
                sysinfo = utils.system_status()
                last_sysinfo = sysinfo
                if sysinfo:
                    print(f"[SYSTEM] load={sysinfo['load1']:.2f} (cores={sysinfo['cores']}) "
                          f"mem_available={sysinfo['mem_available_mb']:.0f}MB "
                          f"swap_used={sysinfo['swap_used_mb']:.0f}MB "
                          f"app_rss={sysinfo['rss_mb']:.0f}MB threads={sysinfo['threads']}"
                          + ("  <- SWAPPING: out of RAM, expect system-wide lag"
                             if sysinfo["swap_used_mb"] > 50 else ""))

            if key == ord('q'):
                break
            elif key == ord('r') or web.take_command() == "recalibrate":
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
                risk_engine.reset_pre_drive()

    finally:
        alerts.close()  # stop any alert still being spoken
        web.close()
        camera.release()
        cv2.destroyAllWindows()
        presence_detector.close()
        face_mesh.close()
        yolo.close()
        log_file.close()
        if risk_log_file is not None:
            risk_log_file.close()
        print(f"Session log saved: {log_path}")


if __name__ == "__main__":
    main()

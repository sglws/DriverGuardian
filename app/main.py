"""DriverGuardian entry point: python -m app.main

One loop, one camera frame at a time:
camera -> face landmarks -> eyes, mouth, head pose -> object detections and
gas readings -> risk engine -> voice, ESP32, seat vibration -> dashboard.
"""

import csv
import os
import time

# Must run before numpy/cv2/mediapipe are imported: thread pools read these once.
_APP_THREADS = str(max(1, (os.cpu_count() or 4) - 2))
os.environ.setdefault("OMP_NUM_THREADS", _APP_THREADS)
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from app import config  # noqa: E402


def _keep_pi_responsive():
    """Lower priority and leave one CPU core to the desktop (Linux only)."""
    if config.APP_NICE and hasattr(os, "nice"):
        try:
            os.nice(config.APP_NICE)
        except OSError as e:
            print(f"[main] could not lower CPU priority: {e}")
    if hasattr(os, "sched_setaffinity"):
        cpus = os.sched_getaffinity(0)
        if len(cpus) > 2:
            os.sched_setaffinity(0, cpus - {max(cpus)})


_keep_pi_responsive()

import cv2  # noqa: E402
import numpy as np  # noqa: E402

cv2.setNumThreads(2)

from app import utils  # noqa: E402
from app.dashboard.session import SessionRecorder  # noqa: E402
from app.dashboard.storage import SessionStore  # noqa: E402
from app.dashboard.testing import TestController  # noqa: E402
from app.dashboard.web_view import WebView  # noqa: E402
from app.outputs.alerts import AlertSystem  # noqa: E402
from app.outputs.arduino import UnoLink  # noqa: E402
from app.risk.risk_engine import PresenceState, Risk, RiskEngine  # noqa: E402
from app.vision.camera import Camera  # noqa: E402
from app.vision.drowsiness import DrowsinessDetector  # noqa: E402
from app.vision.eye_tracker import EyeTracker  # noqa: E402
from app.vision.face_detector import PresenceDetector  # noqa: E402
from app.vision.face_mesh import FaceMeshWrapper  # noqa: E402
from app.vision.head_pose import HeadPoseTracker, estimate_pose  # noqa: E402
from app.vision.mouth_tracker import MouthTracker  # noqa: E402
from app.vision.yolo_detector import YoloProcess  # noqa: E402

RISK_COLORS = {
    Risk.WAITING: (200, 200, 200),
    Risk.SAFE: (0, 200, 0),
    Risk.LOW: (0, 255, 255),
    Risk.MEDIUM: (0, 165, 255),
    Risk.HIGH: (0, 0, 255),
}
STAGES = ("camera", "preprocess", "mediapipe", "presence_logic", "yolo", "risk_draw", "imshow", "waitkey")


def _r(x, nd=3):
    return None if x is None else round(float(x), nd)


# ---------------------------------------------------------------- dashboard state

def dashboard_state(*, risk, debug, messages, presence, face_found, drowsy_state, drowsiness,
                    ear, mar, pose_state, yolo_state, yolo, std_dev, brightness,
                    perf, thermal, sysinfo, links, baseline, calibrating=False, calib_progress=None,
                    paused=False):
    """Everything the web dashboard shows, as plain JSON values."""
    return {
        "risk": risk.name, "case": debug.get("case", "NONE"), "score": debug.get("score"),
        "messages": list(messages[:4]), "presence": presence.name if presence else None,
        "face_found": face_found, "calibrating": calibrating, "calib_progress": calib_progress,
        "paused": paused,
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
            "seatbelt": utils.seatbelt_label(yolo_state.get("seatbelt_off")) if yolo.available else "N/A",
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


# ---------------------------------------------------------------- performance stats

class Stats:
    """Per-stage timing, risk update rate and system health, printed every
    PROFILE_LOG_INTERVAL_SEC and shown on the dashboard."""

    def __init__(self):
        self.max_gap = 1.0 / config.RISK_UPDATE_MIN_HZ
        self.fps = 0.0
        self.stages_ms, self.rate_hz, self.gap_window_ms = {}, None, None
        self.thermal = self.sysinfo = None
        self.updates_session, self.gap_session = 0, 0.0
        self._totals = dict.fromkeys(STAGES, 0.0)
        self._frames = 0
        self._last_print = 0.0
        self._prev_frame = time.monotonic()
        self._last_class = None
        self._segment = 0
        self.restart_window()
        self._risk_log = self._risk_writer = None
        if config.RISK_UPDATE_LOG:
            os.makedirs(config.LOGS_DIR, exist_ok=True)
            path = os.path.join(config.LOGS_DIR, f"risk_updates_{time.strftime('%Y%m%d_%H%M%S')}.csv")
            self._risk_log = open(path, "w", newline="")
            self._risk_writer = csv.writer(self._risk_log)
            self._risk_writer.writerow(["t_monotonic", "risk", "case", "segment"])
            print(f"Logging every risk classification to: {path}")

    def restart_window(self):
        self._updates, self._window_start, self._gap_window = 0, time.monotonic(), 0.0

    def new_session(self):
        self.updates_session, self.gap_session = 0, 0.0

    def not_classifying(self):
        self._last_class = None

    def classified(self, risk, case):
        t = time.monotonic()
        if self._last_class is None:
            self._segment += 1
        else:
            gap = t - self._last_class
            self._gap_window = max(self._gap_window, gap)
            self.gap_session = max(self.gap_session, gap)
        self._last_class = t
        self._updates += 1
        self.updates_session += 1
        if self._risk_writer is not None:
            self._risk_writer.writerow([f"{t:.6f}", risk.name, case, self._segment])

    def perf(self):
        return {"fps": _r(self.fps, 1), "stages_ms": self.stages_ms, "rate_hz": self.rate_hz,
                "gap_window_ms": self.gap_window_ms, "gap_session_ms": _r(self.gap_session * 1000, 0),
                "updates_total": self.updates_session, "camera_fps": config.CAMERA_FPS}

    def frame_done(self, stage_times, now):
        t = time.monotonic()
        if t != self._prev_frame:
            fps = 1.0 / (t - self._prev_frame)
            self.fps = fps if not self.fps else 0.9 * self.fps + 0.1 * fps
        self._prev_frame = t
        for stage, seconds in zip(STAGES, np.diff(stage_times)):
            self._totals[stage] += seconds
        self._frames += 1
        if now - self._last_print >= config.PROFILE_LOG_INTERVAL_SEC:
            self._last_print = now
            self._report()

    def _report(self):
        n = self._frames
        total = sum(self._totals.values())
        print(f"[PROFILE] avg_fps={n / total if total else 0:.1f} over {n} frames | "
              + " ".join(f"{k}={v / n * 1000:.1f}ms" for k, v in self._totals.items()))
        self.stages_ms = {k: round(v / n * 1000, 1) for k, v in self._totals.items()}
        if self._updates:
            rate = self._updates / (time.monotonic() - self._window_start)
            self.rate_hz, self.gap_window_ms = round(rate, 1), round(self._gap_window * 1000)
            verdict = "PASS" if self.gap_session <= self.max_gap else "FAIL"
            print(f"[RISK-RATE] {rate:.1f} Hz | longest gap {self._gap_window * 1000:.0f} ms "
                  f"| session longest {self.gap_session * 1000:.0f} ms: {verdict}")
        self.restart_window()
        self._totals = dict.fromkeys(STAGES, 0.0)
        self._frames = 0

        thermal = utils.check_pi_thermal_status()
        self.thermal = thermal if thermal["available"] else None
        if self.thermal:
            flags = ", ".join(thermal["flags"]) or "no throttling"
            print(f"[THERMAL] {thermal['temp_c']:.1f} C, {flags}")
        self.sysinfo = utils.system_status()
        if self.sysinfo:
            s = self.sysinfo
            print(f"[SYSTEM] load={s['load1']:.2f} mem_available={s['mem_available_mb']:.0f}MB "
                  f"swap_used={s['swap_used_mb']:.0f}MB app_rss={s['rss_mb']:.0f}MB threads={s['threads']}")

    def close(self):
        if self._risk_log is not None:
            self._risk_log.close()


# ---------------------------------------------------------------- local preview window

def draw_boxes(frame, boxes):
    """Green = the box counted towards a detection, yellow = seen but not counted."""
    for x1, y1, x2, y2, label, conf, counted in boxes:
        color = (0, 255, 0) if counted else (255, 255, 0)
        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        cv2.putText(frame, f"{label} {conf:.2f}{'*' if counted else ''}", (int(x1), max(int(y1) - 8, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def draw_panel(frame, *, risk, debug, messages, presence, drowsy, drowsiness, pose, yolo_state,
               ear, mar, std_dev, brightness, fps):
    """Status text for the local window (the dashboard shows the same values)."""
    h, w = frame.shape[:2]
    color = RISK_COLORS[risk]
    cv2.putText(frame, f"RISK: {risk.name}  case={debug.get('case', 'NONE')}  (score={debug.get('score', '-')})",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 3)
    boxes = ", ".join(f"{lbl}:{conf:.2f}{'*' if c else ''}" for *_, lbl, conf, c in yolo_state["raw_boxes"])
    lines = [
        f"Eyes: {'CLOSED' if drowsy['eye_closed'] else 'OPEN'}  EAR={ear:.2f} (thr<{drowsiness.closed_threshold:.2f})  "
        f"closed {drowsy['closed_elapsed']:.1f}s  level={drowsy['level'].name}",
        f"Head pitch: {pose['pitch_label']}  d={pose['pitch_delta']:+.1f}  lean {pose['lean_elapsed']:.1f}s",
        f"Head yaw: {pose['yaw_label']} ({pose['yaw_zone']})  d={pose['yaw_delta']:+.1f}  turn {pose['turn_elapsed']:.1f}s",
        f"Blinks/{config.BLINK_WINDOW_SEC:.0f}s: {drowsy['blink_rate']}  Total: {drowsy['total_blinks']}",
        f"Mouth: {'OPEN' if drowsy['mouth_open'] else 'CLOSED'}  MAR={mar:.2f} (thr>{drowsiness.open_mouth_threshold:.2f})  "
        f"Yawns: {drowsy['total_yawns']}{'  [YAWNING]' if drowsy['is_yawning'] else ''}",
        f"YOLO: phone={yolo_state['phone']} consumption={yolo_state['consumption']} "
        f"cigarette={yolo_state['cigarette']} seatbelt={utils.seatbelt_label(yolo_state['seatbelt_off'])}",
        "Raw boxes: " + (boxes or "(none)"),
        f"Presence: {presence.name}  (std_dev={std_dev:.1f} brightness={brightness:.0f})",
    ]
    y = 58
    for line in lines:
        cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
        y += 19
    y += 8
    for m in messages[:4]:
        cv2.putText(frame, m, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
        y += 22
    cv2.putText(frame, f"FPS: {fps:.1f}", (w - 120, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    cv2.putText(frame, "q=quit  r=recalibrate", (w - 260, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)


def show_window(frame):
    """Shows the frame and returns the key pressed (0xFF = none)."""
    if config.DISPLAY_SCALE != 1.0:
        frame = cv2.resize(frame, None, fx=config.DISPLAY_SCALE, fy=config.DISPLAY_SCALE,
                           interpolation=cv2.INTER_NEAREST)
    cv2.imshow("DriverGuardian", frame)
    return cv2.waitKey(1) & 0xFF


# ---------------------------------------------------------------- main loop

def main():
    print("Starting DriverGuardian...")
    camera = Camera()
    presence_detector = PresenceDetector()
    face_mesh = FaceMeshWrapper()
    eye_tracker = EyeTracker()
    mouth_tracker = MouthTracker()
    drowsiness = DrowsinessDetector()
    head_pose_tracker = HeadPoseTracker()
    yolo = YoloProcess()
    risk_engine = RiskEngine()
    alerts = AlertSystem()
    store = None
    if config.SESSION_HISTORY_ENABLED:
        try:
            store = SessionStore(config.SESSION_DB_PATH, keep=config.SESSION_HISTORY_KEEP)
        except Exception as e:
            print(f"[storage] session history unavailable: {e}")
    recorder = SessionRecorder(store)
    recorder.start()
    web = WebView(recorder, store)
    tests = TestController(say=alerts.say)
    uno = UnoLink()
    stats = Stats()

    presence_hysteresis = utils.Hysteresis(config.NO_FACE_GRACE_SEC, config.PRESENCE_RECOVER_SEC)
    obstruction_hysteresis = utils.Hysteresis(config.OBSTRUCTION_CONFIRM_SEC, config.OBSTRUCTION_RECOVER_SEC)
    display_on = config.DISPLAY_ENABLED
    paused = False
    recalibrate_requested = False
    reported_test = None
    fan_last, fan_prev = -1e9, False
    last_console_log = last_yolo_submit = 0.0
    calibrating, calibration_start, calib_baseline = True, None, None
    calib = {"ear": [], "mar": [], "pitch": [], "yaw": []}

    def sync_tests():
        nonlocal reported_test
        for ev in tests.take_events():
            recorder.log(*ev)
        if tests.result is not None and tests.result is not reported_test:
            reported_test = tests.result
            recorder.add_test(tests.result)

    def links(now, yh=None):
        yh = yh or yolo.health(now)
        return {**alerts.health(now), "yolo": yh["state"], "yolo_age": _r(yh["result_age"], 1),
                "uno": uno.status, "uno_note": uno.note}

    print("Calibration starts once a face is detected: sit normally, look at the camera, eyes open.")

    try:
        while True:
            t0 = time.perf_counter()
            uno.poll(time.monotonic())

            # ---- dashboard commands ----
            stop_requested = False
            for action, body in web.take_commands():
                if action == "stop":
                    stop_requested = True
                elif action == "pause" and not paused:
                    paused = True
                    tests.stop(time.monotonic(), "monitoring paused")
                elif action == "resume" and paused:
                    paused = False
                    stats.restart_window()
                    drowsiness.reset()            # timers kept running while paused
                    head_pose_tracker.clear_lean_case()
                    presence_hysteresis.reset()
                    obstruction_hysteresis.reset()
                elif action in ("mute", "unmute"):
                    alerts.set_muted(action == "mute")
                elif action == "recalibrate":
                    recalibrate_requested = True
                    recorder.log("system", "info", "Recalibration requested", "from the dashboard")
                elif action == "test_start":
                    err = tests.start(body, time.monotonic(), yolo_available=yolo.available)
                    if err:
                        recorder.log("test", "warning", "Test not started", err)
                    else:
                        if paused:
                            paused = False
                            stats.restart_window()
                        recalibrate_requested = recalibrate_requested or tests.needs_calibration
                elif action == "test_stop":
                    tests.stop(time.monotonic())
                elif action == "new_session":
                    tests.stop(time.monotonic(), "new session started")
                    sync_tests()
                    recorder.end("new session started from the dashboard")
                    recorder.start(str(body.get("label") or ""))
                    stats.new_session()
                    paused = False
                    recalibrate_requested = True
            if stop_requested:
                tests.stop(time.monotonic(), "app stopped")
                sync_tests()
                print("[web] stop requested from the dashboard")
                break
            if recalibrate_requested:
                recalibrate_requested = False
                calibrating, calibration_start = True, None
                for values in calib.values():
                    values.clear()
                eye_tracker.reset()
                mouth_tracker.reset()
                drowsiness.reset()
                presence_hysteresis.reset()
                obstruction_hysteresis.reset()
                risk_engine.reset_pre_drive()

            # ---- camera and face ----
            ret, frame = camera.read()
            if not ret:
                print("Camera read failed - stopping.")
                break
            t_camera = time.perf_counter()
            h, w = frame.shape[:2]
            now = time.monotonic()   # never wall-clock: the Pi's clock jumps when it syncs
            stream_due = web.wants_frame(now)
            show = display_on or stream_due

            # Brightness and the covered-lens check use the raw frame (CLAHE would hide a covered lens).
            gray = cv2.cvtColor(cv2.resize(frame, (w // 4, h // 4), interpolation=cv2.INTER_NEAREST),
                                cv2.COLOR_BGR2GRAY)
            std_dev = utils.frame_std_dev(gray)
            brightness = utils.frame_mean_brightness(gray)
            if brightness < config.LOW_LIGHT_BRIGHTNESS_THRESHOLD:
                frame = utils.enhance_low_light(frame)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            t_pre = time.perf_counter()

            landmarks = face_mesh.process(rgb_frame)
            face_found = landmarks is not None
            ear, mar, pitch, yaw = 0.30, 0.5, 0.0, 0.0
            if face_found:
                ear = eye_tracker.update(landmarks, w, h)
                mar = mouth_tracker.update(landmarks, w, h)
                p, y_, _ = estimate_pose(landmarks, w, h)
                if p is not None:
                    pitch, yaw = p, y_
            t_mp = time.perf_counter()

            # ---- calibration: the driver's own baseline ----
            if calibrating:
                if show and face_found:
                    face_mesh.draw(frame, landmarks)
                if stream_due:
                    web.publish(frame.copy() if display_on else frame, now)
                if face_found:
                    calibration_start = calibration_start or now
                    for key, value in zip(calib, (ear, mar, pitch, yaw)):
                        calib[key].append(value)
                    elapsed = now - calibration_start
                    if display_on:
                        cv2.putText(frame, f"CALIBRATING... look straight ahead ({elapsed:.1f}/{config.CALIBRATION_SEC:.0f}s)",
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    if elapsed >= config.CALIBRATION_SEC:
                        calib_baseline = {k: float(np.median(v)) for k, v in calib.items()}
                        drowsiness.set_baseline(calib_baseline["ear"])
                        drowsiness.set_mouth_baseline(calib_baseline["mar"])
                        head_pose_tracker.set_baseline(calib_baseline["pitch"], calib_baseline["yaw"])
                        calibrating = False
                        stats.restart_window()
                        print("Calibration done: " + " ".join(f"{k}={v:.3f}" for k, v in calib_baseline.items()))
                elif display_on:
                    cv2.putText(frame, "Waiting for face to calibrate...", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                alerts.dispatch(Risk.WAITING, ["Calibrating"], "CALIBRATING")   # keeps the ESP32 link alive
                stats.not_classifying()
                if tests.active and not tests.needs_calibration:
                    tests.stop(now, "recalibration started")
                sync_tests()
                if recorder.wants_update(now):
                    progress = min(1.0, (now - calibration_start) / config.CALIBRATION_SEC) if calibration_start else 0.0
                    recorder.update(dict(test=tests.status(now), cabin=uno.state(now), **dashboard_state(
                        risk=Risk.WAITING, debug={"case": "CALIBRATING"},
                        messages=["Calibrating - look straight at the camera"],
                        presence=None, face_found=face_found, drowsy_state=None, drowsiness=drowsiness,
                        ear=ear, mar=mar, pose_state=None, yolo_state=yolo.get_latest(), yolo=yolo,
                        std_dev=std_dev, brightness=brightness,
                        perf={"fps": _r(stats.fps, 1), "stages_ms": stats.stages_ms},
                        thermal=stats.thermal, sysinfo=stats.sysinfo, links=links(now),
                        baseline=calib_baseline, calibrating=True, paused=paused, calib_progress=progress)), now)
                if display_on and show_window(frame) == ord("q"):
                    break
                continue

            # ---- presence, covered camera, head and eyes ----
            # BlazeFace only runs when the landmarker found no face (it is a second opinion).
            presence_face = presence_detector.detect(rgb_frame) if not face_found else False
            if obstruction_hysteresis.update(std_dev < config.FRAME_STD_BLOCKED_THRESHOLD, now):
                presence = PresenceState.CAMERA_BLOCKED
            elif presence_hysteresis.update(not face_found and not presence_face, now):
                presence = PresenceState.DRIVER_ABSENT
            else:
                presence = PresenceState.DRIVER_PRESENT
            pose = head_pose_tracker.update(pitch, yaw, now, face_found=face_found)
            drowsy = drowsiness.update(ear, now, pose["pitch_delta"], mar, face_found=face_found)
            t_presence = time.perf_counter()

            # ---- objects (YOLO gets the frame before anything is drawn on it) ----
            mouth_roi = (lambda: utils.mouth_roi(landmarks, w, h, config.MOUTH_PROXIMITY_RADIUS_MULT)
                         if face_found else None)
            if not tests.blocks_yolo and time.monotonic() - last_yolo_submit >= config.YOLO_INTERVAL_SEC:
                if yolo.submit(frame, mouth_roi()):
                    last_yolo_submit = time.monotonic()
            yolo_state = yolo.get_latest()
            if tests.active:
                tests.update(now, face_found=face_found, drowsy=drowsy, brightness=brightness,
                             yolo_state=yolo_state, frame=frame, yolo=yolo, roi_fn=mouth_roi)
                sync_tests()
            if show and face_found:
                face_mesh.draw(frame, landmarks)
            if show:
                draw_boxes(frame, yolo_state["raw_boxes"])
            if stream_due:
                web.publish(frame.copy() if display_on else frame, now)
            t_yolo = time.perf_counter()

            # ---- risk and outputs ----
            risk, messages, debug = risk_engine.evaluate(
                now, presence, drowsy, pose, yolo_state,
                seatbelt_supported=yolo.available, cabin=uno.state(now), uno_status=uno.status)
            for level, title, detail in risk_engine.pop_events():
                recorder.log("system", level, title, detail)
            if paused:
                risk, messages, debug = Risk.WAITING, ["Monitoring paused"], {"case": "PAUSED", "score": None}
            elif tests.active:
                risk, messages, debug = Risk.WAITING, [tests.title], {"case": "TEST", "score": None}
            case = debug.get("case", "NONE")
            alerts.dispatch(risk, messages, case)

            sleeping = (config.ARDUINO_FAN_SLEEP_SEC is not None and case == "SLEEP"
                        and drowsy["closed_elapsed"] >= config.ARDUINO_FAN_SLEEP_SEC)
            if sleeping and (not fan_prev or now - fan_last >= config.ARDUINO_FAN_REPEAT_SEC) and uno.fan():
                fan_last = now
                recorder.log("system", "warning", "Fan burst",
                             f"Arduino pin 6 on for 3 s (eyes closed {drowsy['closed_elapsed']:.1f} s)")
            fan_prev = sleeping

            if risk == Risk.WAITING:
                stats.not_classifying()
            else:
                stats.classified(risk, case)

            if recorder.wants_update(now):
                yh = yolo.health(now)
                recorder.update(dict(test=tests.status(now), cabin=uno.state(now), **dashboard_state(
                    risk=risk, debug=debug, messages=messages, presence=presence, face_found=face_found,
                    drowsy_state=drowsy, drowsiness=drowsiness, ear=ear, mar=mar,
                    pose_state=pose, yolo_state=yolo_state, yolo=yolo, std_dev=std_dev, brightness=brightness,
                    perf=stats.perf(), thermal=stats.thermal, sysinfo=stats.sysinfo,
                    links=links(now, yh), baseline=calib_baseline, paused=paused)), now)

            if config.CONSOLE_LOG_ENABLED and now - last_console_log >= config.CONSOLE_LOG_INTERVAL_SEC:
                last_console_log = now
                print(f"[{utils.timestamp()}] RISK={risk.name:6s} case={case:16s} score={debug.get('score')} | "
                      f"Eyes={'CLOSED' if drowsy['eye_closed'] else 'OPEN':6s} EAR={ear:.2f} | "
                      f"Pitch={pose['pitch_label']:8s} d={pose['pitch_delta']:+5.1f} | "
                      f"Yaw={pose['yaw_label']:6s} d={pose['yaw_delta']:+5.1f} | {' / '.join(messages[:2])}")

            # ---- local window ----
            t_risk = time.perf_counter()
            key = 0xFF
            if display_on:
                draw_panel(frame, risk=risk, debug=debug, messages=messages, presence=presence, drowsy=drowsy,
                           drowsiness=drowsiness, pose=pose, yolo_state=yolo_state, ear=ear, mar=mar,
                           std_dev=std_dev, brightness=brightness, fps=stats.fps)
                key = show_window(frame)
            t_end = time.perf_counter()
            stats.frame_done((t0, t_camera, t_pre, t_mp, t_presence, t_yolo, t_risk, t_end, t_end), now)

            if key == ord("q"):
                break
            if key == ord("r"):
                recalibrate_requested = True

    finally:
        recorder.end("app stopped")
        if store is not None:
            store.flush()
            store.close()
            print(f"Session saved to the history database: {config.SESSION_DB_PATH}")
        alerts.close()
        uno.close()
        web.close()
        camera.release()
        cv2.destroyAllWindows()
        presence_detector.close()
        face_mesh.close()
        yolo.close()
        stats.close()


if __name__ == "__main__":
    main()

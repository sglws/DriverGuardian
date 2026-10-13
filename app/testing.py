"""
testing.py
----------
Requirement tests started from the dashboard, run inside the live app (same
camera, same perception path, same YOLO process) - no need to stop the app
and run the tools/ scripts over SSH.

  face   Eye-state and yawn accuracy (requirement: >= 90 %). A guided
         script tells the tester what to do (on screen and spoken); what
         they were told is the ground truth, what the app decided is
         compared against it on every frame. Same script and scoring as
         tools/face_accuracy_test.py.
  delay  Object detection delay (requirement: <= 1 s). Each trial: hide the
         object, then show it at the tone. Frames around the tone are kept;
         afterwards YOLO looks at them one by one (no confirmation filter)
         to find the frame where the object really became visible, so the
         tester's reaction time doesn't count. delay = when the live app
         confirmed it - that frame. Same method as tools/detection_delay_test.py.

While a test runs the risk is WAITING (case TEST): no alerts, and the ESP32
holds the car stopped. Results go to the session's event log and summary.
"""

import time

import cv2
import numpy as np

from app import config

REQUIREMENT_ACC = 0.90
DELAY_LIMIT_SEC = 1.0
GUARD_SEC = 0.8             # first part of each step = the tester's reaction time, not scored
READY_SEC = 4.0

# (step, voice prompt, instruction, seconds)
FACE_SCRIPT = [
    ("OPEN",   "T_OPEN",   "Eyes open, look at the camera, mouth closed", 6.0),
    ("CLOSED", "T_CLOSED", "Close your eyes - open them at the next tone", 4.0),
    ("OPEN",   "T_BLINK",  "Eyes open, blink normally", 5.0),
    ("TALK",   "T_TALK",   "Talk or count out loud, eyes open", 6.0),
    ("YAWN",   "T_YAWN",   "Yawn - open your mouth wide and hold it", 6.0),
    ("OPEN",   "T_RELAX",  "Relax - eyes open, mouth closed", 4.0),
]
EYE_LABEL = {"OPEN": "open", "CLOSED": "closed", "TALK": "open", "YAWN": ""}

HIDE_SEC, SHOW_SEC, PRE_ROLL_SEC, CLEAR_SEC = 4.0, 5.0, 0.5, 2.0
OBJECTS = {"phone": "phone", "consumption": "cup or bottle at your mouth", "cigarette": "cigarette"}
RECORD_WIDTH = 640


def score_face(rows):
    """Score face-test rows (dicts; values may be strings when read from a
    CSV). Eye state per frame over OPEN/CLOSED/TALK steps, reported as plain
    and balanced accuracy (open frames outnumber closed ~4:1). Yawning per
    step, exactly as the app decides it: a YAWN step is right if a yawn
    registered, any other step is right if none did."""
    b = lambda v: bool(int(v))
    eye = [r for r in rows if b(r["scored"]) and r["eye_label"]]
    tp = sum(1 for r in eye if r["eye_label"] == "closed" and b(r["eye_closed_pred"]))
    fn = sum(1 for r in eye if r["eye_label"] == "closed" and not b(r["eye_closed_pred"]))
    tn = sum(1 for r in eye if r["eye_label"] == "open" and not b(r["eye_closed_pred"]))
    fp = sum(1 for r in eye if r["eye_label"] == "open" and b(r["eye_closed_pred"]))
    n = tp + fn + tn + fp
    closed_recall = tp / (tp + fn) if tp + fn else 0.0
    open_recall = tn / (tn + fp) if tn + fp else 0.0

    steps = {}
    for r in rows:
        s = steps.setdefault((r.get("condition"), r["round"], r["step_id"]), {"step": r["step"], "yawn": False})
        s["yawn"] |= b(r["is_yawning"])
    yawn_steps = [s for s in steps.values() if s["step"] == "YAWN"]
    other_steps = [s for s in steps.values() if s["step"] in ("OPEN", "TALK", "CLOSED")]
    talk_steps = [s for s in steps.values() if s["step"] == "TALK"]
    hits = sum(s["yawn"] for s in yawn_steps)
    false_yawns = sum(s["yawn"] for s in other_steps)
    ev_n = len(yawn_steps) + len(other_steps)
    mouth = [r for r in rows if b(r["scored"])]
    m_ok = sum(1 for r in mouth if b(r["mouth_open_pred"]) == b(r["yawn_label"]))
    eye_bal = (closed_recall + open_recall) / 2
    yawn_acc = (hits + len(other_steps) - false_yawns) / ev_n if ev_n else 0.0
    return {
        "frames": len(rows),
        "face_found": sum(b(r["face_found"]) for r in rows) / len(rows) if rows else 0.0,
        "low_light": sum(b(r["low_light"]) for r in rows) / len(rows) if rows else 0.0,
        "eye": {"frames": n, "closed_frames": tp + fn, "open_frames": tn + fp,
                "tp": tp, "fn": fn, "tn": tn, "fp": fp,
                "no_face_closed": sum(1 for r in eye if r["eye_label"] == "closed" and not b(r["face_found"])),
                "closed_recall": closed_recall, "open_recall": open_recall,
                "accuracy": (tp + tn) / n if n else 0.0, "balanced": eye_bal,
                "pass": n > 0 and eye_bal >= REQUIREMENT_ACC},
        "yawn": {"steps": len(yawn_steps), "hits": hits, "other_steps": len(other_steps),
                 "false": false_yawns, "talk_steps": len(talk_steps),
                 "talk_false": sum(s["yawn"] for s in talk_steps),
                 "accuracy": yawn_acc, "mouth_frame_acc": m_ok / len(mouth) if mouth else 0.0,
                 "pass": ev_n > 0 and yawn_acc >= REQUIREMENT_ACC},
        "requirement": REQUIREMENT_ACC,
    }


def summarize_delays(trials, limit=DELAY_LIMIT_SEC):
    delays = [t["delay"] for t in trials if t["delay"] is not None]
    missed = sum(1 for t in trials if t["onset"] is not None and t["delay"] is None)
    srt = sorted(delays)
    return {
        "measured": len(delays), "trials_n": len(trials), "missed": missed,
        "mean": sum(delays) / len(delays) if delays else None,
        "median": srt[len(srt) // 2] if srt else None,
        "max": max(delays) if delays else None,
        "limit": limit, "pass": bool(delays) and max(delays) <= limit and missed == 0,
    }


class TestController:
    def __init__(self, say=None):
        self._say = say or (lambda key, now: None)
        self.kind = None
        self.result = None          # last finished test (shown on the dashboard)
        self._events = []           # (kind, level, title, detail) for the session log
        self._seq = 0               # bumps on every new instruction (dashboard beeps)

    # ------------------------------------------------------------ control

    @property
    def active(self):
        return self.kind is not None

    @property
    def blocks_yolo(self):
        """The delay test's analysis needs the YOLO process to itself."""
        return self.kind == "delay" and self.phase == "analyse"

    @property
    def needs_calibration(self):
        return self.kind == "face" and self.phase == "calibrate"

    def start(self, params, now, yolo_available=True):
        """Returns an error message, or None when the test has started."""
        if self.active:
            return "a test is already running"
        test = params.get("test")
        clamp = lambda v, lo, hi, d: max(lo, min(hi, int(v))) if str(v).strip().lstrip("-").isdigit() else d
        if test == "face":
            self.rounds = clamp(params.get("rounds", 2), 1, 5, 2)
            self.condition = (str(params.get("condition") or "normal").strip() or "normal")[:40]
            self.rows, self.round, self.step_i, self.step_id = [], 1, -1, 0
            self.phase = "calibrate"       # a fresh baseline first, like the tool
        elif test == "delay":
            if not yolo_available:
                return "object detection (YOLO) is not available"
            obj = params.get("object", "phone")
            if obj not in OBJECTS:
                return "unknown object"
            self.obj, self.trials_n = obj, clamp(params.get("trials", 5), 1, 10, 5)
            self.trial, self.trials = 0, []
            self.phase = "ready"
        else:
            return "unknown test"
        self.kind, self.t0, self.phase_at = test, now, now
        self._instr, self._key = "", None
        self._events.append(("test", "info", f"{self.title} started", self._params_text()))
        if self.phase == "ready":
            self._instruct("T_READY", "Get ready - follow the instructions", now)
        return None

    def stop(self, now, reason="stopped from the dashboard"):
        if not self.active:
            return
        self._finish(now, aborted=reason)

    def take_events(self):
        ev, self._events = self._events, []
        return ev

    @property
    def title(self):
        if self.kind == "face":
            return "Face accuracy test"
        if self.kind == "delay":
            return f"Detection delay test ({self.obj})"
        return "Test"

    def _params_text(self):
        if self.kind == "face":
            return f"{self.rounds} round{'s' if self.rounds > 1 else ''}, condition: {self.condition}"
        return f"{self.trials_n} trial{'s' if self.trials_n > 1 else ''}, object: {OBJECTS[self.obj]}"

    def _instruct(self, key, text, now):
        self._instr, self._key = text, key
        self._seq += 1
        if key:
            self._say(key, now)

    # ------------------------------------------------------------ per frame

    def update(self, now, *, calibrating=False, face_found=False, drowsy=None, brightness=None,
               yolo_state=None, frame=None, roi_fn=None, yolo=None):
        """Advance the running test. Called every frame by the main loop."""
        if not self.active:
            return
        if self.kind == "face":
            self._face(now, calibrating, face_found, drowsy, brightness)
        else:
            self._delay(now, yolo_state or {}, frame, roi_fn, yolo)

    def _face(self, now, calibrating, face_found, drowsy, brightness):
        if self.phase == "calibrate":
            if not calibrating:
                self.phase, self.phase_at = "ready", now
                self._instruct("T_READY", "Get ready - follow the instructions", now)
            return
        if self.phase == "ready":
            if now - self.phase_at >= READY_SEC:
                self.phase = "run"
                self._next_step(now)
            return
        step, _, _, dur = FACE_SCRIPT[self.step_i]
        t_in = now - self.phase_at
        if t_in >= dur:
            self._next_step(now)
            if not self.active:
                return
            step, t_in = FACE_SCRIPT[self.step_i][0], 0.0
        if drowsy is None:
            return
        self.rows.append({
            "condition": self.condition, "round": self.round, "step_id": self.step_id, "step": step,
            "scored": int(t_in >= GUARD_SEC), "eye_label": EYE_LABEL[step], "yawn_label": int(step == "YAWN"),
            "face_found": int(face_found), "eye_closed_pred": int(drowsy["eye_closed"]),
            "mouth_open_pred": int(drowsy["mouth_open"]), "is_yawning": int(drowsy["is_yawning"]),
            "low_light": int(brightness is not None and brightness < config.LOW_LIGHT_BRIGHTNESS_THRESHOLD),
        })
        self._sees = (f"eyes {'closed' if drowsy['eye_closed'] else 'open'}, "
                      f"mouth {'open' if drowsy['mouth_open'] else 'closed'}"
                      f"{', yawn' if drowsy['is_yawning'] else ''}{'' if face_found else ', no face'}")

    def _next_step(self, now):
        self.step_i += 1
        if self.step_i >= len(FACE_SCRIPT):
            if self.round >= self.rounds:
                self._finish(now)
                return
            self.round += 1
            self.step_i = 0
        self.step_id += 1
        self.phase_at = now
        _, key, text, _ = FACE_SCRIPT[self.step_i]
        self._instruct(key, text, now)

    def _delay(self, now, yolo_state, frame, roi_fn, yolo):
        el = now - self.phase_at
        if self.phase == "ready":
            if el >= READY_SEC:
                self._start_trial(now)
            return
        if self.phase == "clear":
            if el >= CLEAR_SEC or not yolo_state.get(self.obj):
                self._start_trial(now)
            return
        if self.phase in ("hide", "show"):
            tr = self.trials[-1]
            if self.phase == "hide" and el >= HIDE_SEC:
                self.phase, self.phase_at, tr["cue"] = "show", now, now
                self._instruct("T_SHOW", f"SHOW the {OBJECTS[self.obj]} now and hold it in view", now)
                el = 0.0
            if self.phase == "show" and tr["confirmed"] is None and yolo_state.get(self.obj):
                tr["confirmed"] = now
            if frame is not None and (self.phase == "show" or el >= HIDE_SEC - PRE_ROLL_SEC):
                h, w = frame.shape[:2]
                s = RECORD_WIDTH / w
                small = cv2.resize(frame, (RECORD_WIDTH, round(h * s)), interpolation=cv2.INTER_AREA)
                ok, jpg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 90])
                roi = roi_fn() if (roi_fn and self.obj != "phone") else None
                if ok:
                    tr["frames"].append((now, jpg, tuple(v * s for v in roi) if roi else None))
            self._sees = f"{self.obj} {'detected' if yolo_state.get(self.obj) else 'not detected'}"
            if self.phase == "show" and el >= SHOW_SEC:
                if self.trial < self.trials_n:
                    if yolo_state.get(self.obj):
                        self.phase, self.phase_at = "clear", now
                        self._instruct(None, f"Put the {OBJECTS[self.obj]} away", now)
                    else:
                        self._start_trial(now)
                else:
                    self.phase, self.phase_at = "analyse", now
                    self._ai, self._fi, self._waiting = 0, 0, False
                    self._analysed = 0
                    self._instruct(None, "Analysing the recorded frames…", now)
            return
        if self.phase == "analyse":
            self._analyse(now, yolo)

    def _start_trial(self, now):
        self.trial += 1
        self.trials.append({"n": self.trial, "cue": None, "confirmed": None, "frames": [], "onset": None})
        self.phase, self.phase_at = "hide", now
        self._instruct("T_HIDE", f"HIDE the {OBJECTS[self.obj]} - keep it out of view", now)

    def _analyse(self, now, yolo):
        """One recorded frame at a time through YOLO, until the onset of
        each trial is found."""
        if yolo is None:
            self._finish(now, aborted="object detection unavailable")
            return
        while self._ai < len(self.trials):
            tr = self.trials[self._ai]
            frames = [f for f in tr["frames"] if tr["cue"] is not None and f[0] >= tr["cue"] - PRE_ROLL_SEC]
            if self._fi >= len(frames):                      # never visible
                self._ai, self._fi = self._ai + 1, 0
                continue
            if self._waiting:
                raw = yolo.take_raw()
                if raw is None:
                    if now - self._sent_at > 15.0:
                        self._finish(now, aborted="object detection stopped responding")
                    return
                self._waiting = False
                self._analysed += 1
                if raw.get(self.obj):
                    tr["onset"] = frames[self._fi][0]
                    self._ai, self._fi = self._ai + 1, 0
                else:
                    self._fi += 1
                continue
            t_frame, jpg, roi = frames[self._fi]
            img = cv2.imdecode(np.frombuffer(jpg.tobytes(), np.uint8), cv2.IMREAD_COLOR)
            if yolo.submit_raw(img, roi):
                self._waiting, self._sent_at = True, now
                raw = yolo.take_raw() if yolo._fallback is not None else None
                if raw is not None:                          # synchronous fallback
                    self._waiting = False
                    self._analysed += 1
                    if raw.get(self.obj):
                        tr["onset"] = t_frame
                        self._ai, self._fi = self._ai + 1, 0
                    else:
                        self._fi += 1
            return
        self._finish(now)

    # ------------------------------------------------------------ results

    def _finish(self, now, aborted=None):
        kind = self.kind
        res = {"test": kind, "title": self.title, "ts": time.time(), "duration_s": round(now - self.t0, 1),
               "aborted": aborted}
        if kind == "face":
            res.update(condition=self.condition, rounds=self.rounds, rounds_done=self.round,
                       **score_face(self.rows))
            ok = res["frames"] > 0
            e, y = res["eye"], res["yawn"]
            passed = ok and e["pass"] and y["pass"]
            detail = (f"eyes {100 * e['balanced']:.1f}% (balanced), yawns {100 * y['accuracy']:.1f}% "
                      f"({y['hits']}/{y['steps']} detected, {y['false']} false)" if ok else "no data recorded")
        else:
            trials = []
            for t in self.trials:
                if t["cue"] is None:
                    continue
                delay = (t["confirmed"] - t["onset"]) if (t["onset"] is not None and t["confirmed"] is not None) else None
                trials.append({"n": t["n"],
                               "onset": None if t["onset"] is None else round(t["onset"] - t["cue"], 2),
                               "confirmed": None if t["confirmed"] is None else round(t["confirmed"] - t["cue"], 2),
                               "delay": None if delay is None else round(delay, 2)})
            if self.phase != "analyse" or aborted:
                trials = [dict(t, onset=None, delay=None) for t in trials]   # never analysed
            res.update(object=self.obj, trials=trials, **summarize_delays(trials))
            passed = res["pass"]
            detail = (f"max {res['max']:.2f} s, mean {res['mean']:.2f} s, {res['measured']}/{res['trials_n']} measured"
                      + (f", {res['missed']} never confirmed" if res["missed"] else "")) if res["measured"] else "no trial could be measured"
        res["passed"] = bool(passed) and not aborted
        self.result = res
        self.kind = None
        if aborted:
            self._events.append(("test", "warning", f"{res['title']} stopped", f"{aborted}, {detail}"))
        else:
            self._events.append(("test", "good" if passed else "critical",
                                 f"{res['title']}: {'PASS' if passed else 'FAIL'}", detail))
            self._say("T_DONE", now)
        self._seq += 1

    def status(self, now):
        """For the dashboard."""
        st = {"active": self.active, "seq": self._seq, "result": self.result}
        if not self.active:
            return st
        st.update(kind=self.kind, title=self.title, phase=self.phase, instruction=self._instr,
                  sees=getattr(self, "_sees", ""), params=self._params_text())
        el = now - self.phase_at
        if self.kind == "face":
            if self.phase == "calibrate":
                st.update(instruction="Calibrating - look straight at the camera", progress=0.0)
            elif self.phase == "ready":
                st.update(remaining=max(0.0, READY_SEC - el), progress=0.0, step="Get ready")
            else:
                step, _, _, dur = FACE_SCRIPT[self.step_i]
                total = len(FACE_SCRIPT) * self.rounds
                done = (self.round - 1) * len(FACE_SCRIPT) + self.step_i
                st.update(remaining=max(0.0, dur - el), progress=(done + min(1.0, el / dur)) / total,
                          step=f"Round {self.round}/{self.rounds}, step {self.step_i + 1}/{len(FACE_SCRIPT)}",
                          eyes_closed_step=step == "CLOSED")
        else:
            if self.phase == "analyse":
                total = sum(len(t["frames"]) for t in self.trials) or 1
                st.update(progress=min(1.0, self._analysed / total), step="Analysing",
                          sees=f"{self._analysed} frames checked, trial {min(self._ai + 1, len(self.trials))}/{len(self.trials)}")
            else:
                dur = {"ready": READY_SEC, "hide": HIDE_SEC, "show": SHOW_SEC, "clear": CLEAR_SEC}[self.phase]
                per = HIDE_SEC + SHOW_SEC
                done = max(0, self.trial - 1) * per + (el if self.phase == "hide" else HIDE_SEC + el if self.phase == "show" else per if self.phase == "clear" else 0)
                st.update(remaining=max(0.0, dur - el), progress=min(1.0, done / (per * self.trials_n)) * 0.85,
                          step=f"Trial {max(1, self.trial)}/{self.trials_n}" if self.phase != "ready" else "Get ready",
                          show=self.phase == "show")
        return st

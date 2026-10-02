"""Compare the square YOLO model with the 16:9 export on the same frames.

The 16:9 model (models/best_384x640_ncnn_model, config.YOLO_USE_16X9_MODEL)
does ~40% less work per inference. Before switching to it, check that it
detects the same things as the current square model. Both models see the
same frames, prepared exactly the way the app prepares them (downscaled to
640 px wide), and their results go through the app's own per-class
thresholds - so a "detection" here means the same thing as in the app.

Stop the app first (the camera can only be opened by one program).

Usage (on the Pi, in front of the camera):
    python tools/compare_yolo_models.py                 # 60 s live from the camera
    python tools/compare_yolo_models.py --seconds 120
    python tools/compare_yolo_models.py --video clip.mp4
    python tools/compare_yolo_models.py --images some/folder

During a live run, show everything the model knows: hold a phone, drink from
a cup/bottle, eat something, hold a cigarette (or a pen like one), seatbelt on
and off. Frames where the two models disagree are saved to
logs/model_compare_<time>/ for inspection.
"""
import argparse
import glob
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402

from app import config  # noqa: E402

CLASSES = ("phone", "consumption", "cigarette", "seatbelt")
SQUARE = (os.path.join(config.MODELS_DIR, "best_ncnn_model"), 640)
RECT = (os.path.join(config.MODELS_DIR, "best_384x640_ncnn_model"), (384, 640))


def load(path, imgsz):
    from app.yolo_detector import YoloDetector, _load_backends
    _load_backends()
    det = YoloDetector.__new__(YoloDetector)        # same detect() logic as the app
    from app import yolo_detector
    det.model = yolo_detector.YOLO(path, task="detect")
    det.using_finetuned = True
    det.class_names = det.model.names
    det.imgsz = imgsz
    return det


def run_detector(det, frame):
    old = config.YOLO_IMG_SIZE
    config.YOLO_IMG_SIZE = det.imgsz
    try:
        t = time.perf_counter()
        r = det.detect(frame)
        return r, (time.perf_counter() - t) * 1000
    finally:
        config.YOLO_IMG_SIZE = old


def flags(result):
    """Per-class 'detected' exactly as the app counts it (before K-of-N voting)."""
    return {
        "phone": bool(result["phone"]),
        "consumption": bool(result["consumption"]),
        "cigarette": bool(result["cigarette"]),
        "seatbelt": result["seatbelt_off"] is False,
    }


def top_conf(result, cls):
    names = {"phone": ("phone",), "consumption": ("drink", "eating", "food", "cup", "bottle"),
             "cigarette": ("cigarette", "smoking"), "seatbelt": ("belt",)}[cls]
    confs = [b[5] for b in result["raw_boxes"] if b[6] and any(n in b[4].lower() for n in names)]
    return max(confs) if confs else None


def frames(args):
    if args.images:
        for p in sorted(glob.glob(os.path.join(args.images, "*"))):
            img = cv2.imread(p)
            if img is not None:
                yield img
    elif args.video:
        cap = cv2.VideoCapture(args.video)
        n = 0
        while True:
            ok, img = cap.read()
            if not ok:
                break
            n += 1
            if n % args.every == 0:
                yield img
    else:
        from app.camera import Camera
        cam = Camera()
        try:
            end = time.monotonic() + args.seconds
            print(f"Recording for {args.seconds} s - show phone, cup/bottle, food, "
                  f"cigarette (or a pen), seatbelt on and off...")
            while time.monotonic() < end:
                ok, img = cam.read()
                if ok:
                    yield img
        finally:
            cam.release()


def main():
    ap = argparse.ArgumentParser(description="Compare the square and 16:9 YOLO models.")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--video", help="video file instead of the camera")
    src.add_argument("--images", help="folder of images instead of the camera")
    ap.add_argument("--seconds", type=int, default=60, help="live recording length (default 60)")
    ap.add_argument("--every", type=int, default=3, help="video: use every Nth frame (default 3)")
    args = ap.parse_args()

    for path, _ in (SQUARE, RECT):
        if not os.path.isdir(path):
            sys.exit(f"Missing model: {path}")
    print("Loading both models...")
    sq, rc = load(*SQUARE), load(*RECT)
    out_dir = os.path.join(config.LOGS_DIR, f"model_compare_{time.strftime('%Y%m%d_%H%M%S')}")

    n = 0
    stats = {c: {"sq": 0, "rc": 0, "both": 0, "agree": 0, "conf_sq": [], "conf_rc": []} for c in CLASSES}
    t_sq, t_rc, saved = [], [], 0
    for frame in frames(args):
        h, w = frame.shape[:2]
        if w > 640:                                         # same as YoloProcess.submit()
            frame = cv2.resize(frame, (640, round(h * 640 / w)), interpolation=cv2.INTER_AREA)
        r_sq, ms_sq = run_detector(sq, frame)
        r_rc, ms_rc = run_detector(rc, frame)
        if n >= 2:                                          # skip warm-up timings
            t_sq.append(ms_sq)
            t_rc.append(ms_rc)
        f_sq, f_rc = flags(r_sq), flags(r_rc)
        disagree = []
        for c in CLASSES:
            s = stats[c]
            s["sq"] += f_sq[c]
            s["rc"] += f_rc[c]
            s["both"] += f_sq[c] and f_rc[c]
            s["agree"] += f_sq[c] == f_rc[c]
            if f_sq[c] and f_rc[c]:
                s["conf_sq"].append(top_conf(r_sq, c))
                s["conf_rc"].append(top_conf(r_rc, c))
            if f_sq[c] != f_rc[c]:
                disagree.append(f"{c}-{'square' if f_sq[c] else '16x9'}only")
        if disagree and saved < 200:
            os.makedirs(out_dir, exist_ok=True)
            cv2.imwrite(os.path.join(out_dir, f"{n:05d}_{'_'.join(disagree)}.jpg"), frame)
            saved += 1
        n += 1
        if n % 20 == 0:
            print(f"  {n} frames compared...")

    if n == 0:
        sys.exit("No frames.")
    mean = lambda xs: sum(x for x in xs if x is not None) / max(1, sum(x is not None for x in xs))
    print(f"\n=== {n} frames ===")
    print(f"{'class':12s} {'square':>7s} {'16:9':>7s} {'both':>6s} {'agree':>7s} {'conf sq/16:9 (both)':>22s}")
    worst = 100.0
    for c in CLASSES:
        s = stats[c]
        agree = 100 * s["agree"] / n
        worst = min(worst, agree) if (s["sq"] or s["rc"]) else worst
        conf = (f"{mean(s['conf_sq']):.2f} / {mean(s['conf_rc']):.2f}" if s["both"] else "-")
        print(f"{c:12s} {s['sq']:7d} {s['rc']:7d} {s['both']:6d} {agree:6.1f}% {conf:>22s}")
    if t_sq:
        ts, tr = sorted(t_sq), sorted(t_rc)
        print(f"\nTime per detection (median): square {ts[len(ts) // 2]:.0f} ms | 16:9 {tr[len(tr) // 2]:.0f} ms "
              f"({100 * (1 - tr[len(tr) // 2] / ts[len(ts) // 2]):.0f}% faster)")
    if saved:
        print(f"{saved} disagreeing frames saved to {out_dir}")
    covered = [c for c in CLASSES if stats[c]["sq"] or stats[c]["rc"]]
    print(f"\nClasses seen: {', '.join(covered) or 'none'}"
          + ("" if len(covered) == len(CLASSES) else f"  (not tested: {', '.join(c for c in CLASSES if c not in covered)})"))
    verdict = "EQUIVALENT - safe to switch" if worst >= 95 and covered else \
              "CHECK the saved frames before switching" if covered else "INCONCLUSIVE - nothing was detected"
    print(f"Lowest per-class agreement: {worst:.1f}%  ->  {verdict}")
    print("(Switch with YOLO_USE_16X9_MODEL = True in app/config.py, or DG_16X9=1 for one run.)")


if __name__ == "__main__":
    main()

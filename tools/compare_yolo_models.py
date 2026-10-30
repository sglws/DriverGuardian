"""Compare YOLO models on the same frames.

Two uses:

1. Different trained models (e.g. 22 Oct on main vs 29 Oct vs 30 Oct), taken
   straight from their git branches - nothing to copy to the Pi:
       python tools/compare_yolo_models.py --models main 29oct 30oct
   A model can also be a folder holding an NCNN export (or a best.pt):
       python tools/compare_yolo_models.py --models main ~/old_models/best_ncnn_model
   Branches must be fetched first (git fetch); origin/<branch> works too.

2. Without --models: the square model against the 16:9 export of the same
   weights (models/best_384x640_ncnn_model, config.YOLO_USE_16X9_MODEL), which
   does ~40% less work per inference - check they detect the same things
   before switching.

Every model sees the same frames, prepared exactly the way the app prepares
them (downscaled to 640 px wide), and its results go through the app's own
per-class thresholds and mouth rule - so a "detection" here means the same
thing as in the app (before the 2-of-3 confirmation).

Stop the app first (the camera can only be opened by one program).

Usage (on the Pi, in front of the camera):
    python tools/compare_yolo_models.py --models main 30oct              # 60 s live
    python tools/compare_yolo_models.py --models main 30oct --seconds 120
    python tools/compare_yolo_models.py --models main 30oct --video clip.mp4
    python tools/compare_yolo_models.py --models main 30oct --images some/folder
    add --16x9 to compare the branches' 384x640 exports instead of the square ones

During a live run, show everything the model knows: hold a phone, drink from
a cup/bottle, eat something, hold a cigarette (or a pen like one), seatbelt on
and off. Frames where the models disagree are saved to
logs/model_compare_<time>/, named after who saw what, e.g.
00123_seatbelt-main.jpg = only main saw a seatbelt there. Those frames show
where a model fails, and are good images to add to the dataset.
"""
import argparse
import glob
import os
import subprocess
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402

from app import config  # noqa: E402

ROOT = config.BASE_DIR
CLASSES = ("phone", "consumption", "cigarette", "seatbelt")
SQUARE = ("square", os.path.join(config.MODELS_DIR, "best_ncnn_model"), 640)
RECT = ("16x9", os.path.join(config.MODELS_DIR, "best_384x640_ncnn_model"), (384, 640))


def _git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, check=True).stdout


def from_branch(branch, sub):
    """Extract models/<sub> from a branch into logs/compare_models/ (cached per commit)."""
    for ref in (branch, f"origin/{branch}"):
        try:
            sha = _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").decode().strip()
            break
        except subprocess.CalledProcessError:
            continue
    else:
        sys.exit(f"No branch '{branch}' - run 'git fetch' first, or give a folder path.")
    out = os.path.join(config.LOGS_DIR, "compare_models", f"{branch.replace('/', '_')}_{sha[:8]}", sub)
    if not os.path.isdir(out):
        files = _git("ls-tree", "--name-only", sha, f"models/{sub}/").decode().split()
        if not files:
            sys.exit(f"Branch '{branch}' has no models/{sub}.")
        os.makedirs(out)
        for f in files:
            with open(os.path.join(out, os.path.basename(f)), "wb") as fh:
                fh.write(_git("show", f"{sha}:{f}"))
    return out


def resolve(spec, rect):
    """'main' / '30oct' -> that branch's export; a folder or .pt path -> itself."""
    sub, imgsz = ("best_384x640_ncnn_model", (384, 640)) if rect else ("best_ncnn_model", 640)
    path = os.path.expanduser(spec)
    if os.path.exists(path):
        return os.path.basename(os.path.normpath(path)), path, imgsz
    return spec, from_branch(spec, sub), imgsz


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
    ap = argparse.ArgumentParser(description="Compare YOLO models on the same frames.")
    ap.add_argument("--models", nargs="+", metavar="BRANCH_OR_PATH",
                    help="2 or more git branches (main, 29oct, ...) or model folders; "
                         "default: square vs 16:9 export of models/")
    ap.add_argument("--16x9", dest="rect", action="store_true",
                    help="with --models: use the branches' 384x640 exports")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--video", help="video file instead of the camera")
    src.add_argument("--images", help="folder of images instead of the camera")
    ap.add_argument("--seconds", type=int, default=60, help="live recording length (default 60)")
    ap.add_argument("--every", type=int, default=3, help="video: use every Nth frame (default 3)")
    args = ap.parse_args()

    if args.models:
        if len(args.models) < 2:
            sys.exit("Give at least 2 models to compare.")
        specs = [resolve(m, args.rect) for m in args.models]
    else:
        specs = [SQUARE, RECT]
        for _, path, _ in specs:
            if not os.path.isdir(path):
                sys.exit(f"Missing model: {path}")
    names = [s[0] for s in specs]
    if len(set(names)) < len(names):
        sys.exit(f"Two models have the same name: {names}")
    print("Loading " + ", ".join(f"{n} ({p})" for n, p, _ in specs) + "...")
    dets = [load(p, s) for _, p, s in specs]
    out_dir = os.path.join(config.LOGS_DIR, f"model_compare_{time.strftime('%Y%m%d_%H%M%S')}")

    n, saved = 0, 0
    count = {c: [0] * len(dets) for c in CLASSES}          # frames each model detected c in
    agree = {c: 0 for c in CLASSES}                         # frames where all models gave the same answer
    confs = {c: [[] for _ in dets] for c in CLASSES}       # confidence on frames all models detected c
    times = [[] for _ in dets]
    for frame in frames(args):
        h, w = frame.shape[:2]
        if w > 640:                                         # same as YoloProcess.submit()
            frame = cv2.resize(frame, (640, round(h * 640 / w)), interpolation=cv2.INTER_AREA)
        results = []
        for i, det in enumerate(dets):
            r, ms = run_detector(det, frame)
            results.append(r)
            if n >= 2:                                      # skip warm-up timings
                times[i].append(ms)
        fl = [flags(r) for r in results]
        disagree = []
        for c in CLASSES:
            seen = [f[c] for f in fl]
            for i, s in enumerate(seen):
                count[c][i] += s
            if all(seen):
                for i, r in enumerate(results):
                    confs[c][i].append(top_conf(r, c))
            if len(set(seen)) == 1:
                agree[c] += 1
            else:
                disagree.append(f"{c}-{'+'.join(names[i] for i, s in enumerate(seen) if s)}")
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
    w = max(8, *(len(x) for x in names))
    print(f"\n=== {n} frames: frames with a detection, per model ===")
    print(f"{'class':12s} " + " ".join(f"{x:>{w}s}" for x in names) + f" {'agree':>7s}   mean conf when all detect")
    worst = 100.0
    for c in CLASSES:
        pct = 100 * agree[c] / n
        if any(count[c]):
            worst = min(worst, pct)
        conf = " / ".join(f"{mean(x):.2f}" for x in confs[c]) if confs[c][0] else "-"
        print(f"{c:12s} " + " ".join(f"{k:{w}d}" for k in count[c]) + f" {pct:6.1f}%   {conf}")
    if times[0]:
        med = [sorted(t)[len(t) // 2] for t in times]
        print("\nTime per detection (median): " + " | ".join(f"{x} {m:.0f} ms" for x, m in zip(names, med)))
    if saved:
        print(f"{saved} disagreeing frames saved to {out_dir}")
        print("  (file name = which model(s) saw it, e.g. seatbelt-main = only main saw a seatbelt)")
    covered = [c for c in CLASSES if any(count[c])]
    print(f"\nClasses seen: {', '.join(covered) or 'none'}"
          + ("" if len(covered) == len(CLASSES) else f"  (not tested: {', '.join(c for c in CLASSES if c not in covered)})"))
    if args.models:
        print(f"Lowest per-class agreement: {worst:.1f}%")
        print("Who is right? Count is not accuracy - more seatbelt frames is better only if the belt was on.\n"
              "Look at the saved frames: each one shows what you were really doing.")
    else:
        verdict = "EQUIVALENT - safe to switch" if worst >= 95 and covered else \
                  "CHECK the saved frames before switching" if covered else "INCONCLUSIVE - nothing was detected"
        print(f"Lowest per-class agreement: {worst:.1f}%  ->  {verdict}")
        print("(Switch with YOLO_USE_16X9_MODEL = True in app/config.py, or DG_16X9=1 for one run.)")


if __name__ == "__main__":
    main()

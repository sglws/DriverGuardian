"""Compare 2+ YOLO models on the same frames (live camera, a video or images).

    python tools/compare_yolo_models.py --models main 3nov

A model is a git branch (its models/best_ncnn_model) or a model folder. Frames where
the models disagree are saved to logs/ so you can see which one was right.
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


def resolve(spec):
    """'main' / '3nov' -> that branch's NCNN export; a folder or .pt path -> itself."""
    path = os.path.expanduser(spec)
    if os.path.exists(path):
        return os.path.basename(os.path.normpath(path)), path
    return spec, from_branch(spec, "best_ncnn_model")


def load(path):
    """A YoloDetector (same detect() as the app) running the model at `path`."""
    from ultralytics import YOLO
    from app.vision.yolo_detector import YoloDetector
    det = YoloDetector.__new__(YoloDetector)
    det.model = YOLO(path, task="detect")
    return det


def run_detector(det, frame):
    t = time.perf_counter()
    r = det.detect(frame)
    return r, (time.perf_counter() - t) * 1000


def flags(result):
    """Per-class 'detected' as the app counts it (before the 2-of-3 confirmation)."""
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
        from app.vision.camera import Camera
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
    ap.add_argument("--models", nargs="+", metavar="BRANCH_OR_PATH", required=True,
                    help="2 or more git branches (main, 3nov, ...) or model folders")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--video", help="video file instead of the camera")
    src.add_argument("--images", help="folder of images instead of the camera")
    ap.add_argument("--seconds", type=int, default=60, help="live recording length (default 60)")
    ap.add_argument("--every", type=int, default=3, help="video: use every Nth frame (default 3)")
    args = ap.parse_args()

    if len(args.models) < 2:
        sys.exit("Give at least 2 models to compare.")
    specs = [resolve(m) for m in args.models]
    names = [s[0] for s in specs]
    if len(set(names)) < len(names):
        sys.exit(f"Two models have the same name: {names}")
    print("Loading " + ", ".join(f"{n} ({p})" for n, p in specs) + "...")
    dets = [load(p) for _, p in specs]
    out_dir = os.path.join(config.LOGS_DIR, f"model_compare_{time.strftime('%Y%m%d_%H%M%S')}")

    n, saved = 0, 0
    count = {c: [0] * len(dets) for c in CLASSES}
    agree = {c: 0 for c in CLASSES}
    confs = {c: [[] for _ in dets] for c in CLASSES}
    times = [[] for _ in dets]
    for frame in frames(args):
        h, w = frame.shape[:2]
        if w > 640:
            frame = cv2.resize(frame, (640, round(h * 640 / w)), interpolation=cv2.INTER_AREA)
        results = []
        for i, det in enumerate(dets):
            r, ms = run_detector(det, frame)
            results.append(r)
            if n >= 2:
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
    print(f"Lowest per-class agreement: {worst:.1f}%")
    print("Who is right? Count is not accuracy - more seatbelt frames is better only if the belt was on.\n"
          "Look at the saved frames: each one shows what you were really doing.")


if __name__ == "__main__":
    main()

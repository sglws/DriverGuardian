"""Export models/best.pt for the Pi (NCNN by default, the fastest on its CPU).

    python training/export.py [--format ncnn|onnx]

The NCNN export lands in models/best_ncnn_model, which the app uses automatically.
Re-export every time best.pt changes.
"""

import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import config  # noqa: E402

try:
    from ultralytics import YOLO
except ImportError:
    raise SystemExit("Install ultralytics first: pip install ultralytics")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--format", default="ncnn", choices=["ncnn", "onnx"])
    args = parser.parse_args()
    if not os.path.exists(config.YOLO_MODEL_PATH):
        raise SystemExit(f"No model at {config.YOLO_MODEL_PATH}.")
    path = YOLO(config.YOLO_MODEL_PATH).export(format=args.format, imgsz=config.YOLO_IMG_SIZE)
    print(f"Exported to: {path}")


if __name__ == "__main__":
    main()

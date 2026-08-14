"""
export.py
---------
Phase 15 deliverable: export the fine-tuned model to a Raspberry-Pi-
friendly inference format (ONNX by default; NCNN is worth trying too,
since it's typically fastest on Pi's ARM CPU).

Usage:
    python training/export.py --format onnx
    python training/export.py --format ncnn
"""

import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import config

try:
    from ultralytics import YOLO
except ImportError:
    raise SystemExit("Install ultralytics first: pip install ultralytics")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", default="onnx", choices=["onnx", "ncnn", "tflite", "openvino"])
    args = parser.parse_args()

    if not os.path.exists(config.YOLO_FINETUNED_PATH):
        raise SystemExit(f"No fine-tuned model found at {config.YOLO_FINETUNED_PATH}.")

    model = YOLO(config.YOLO_FINETUNED_PATH)
    exported_path = model.export(format=args.format, imgsz=config.YOLO_IMG_SIZE)
    print(f"Exported to: {exported_path}")
    print("Copy this file to the Raspberry Pi and point yolo_detector.py at it "
          "(update YOLO_FINETUNED_PATH in config.py, or swap the loader for the "
          "exported runtime's API if it differs from ultralytics.YOLO).")


if __name__ == "__main__":
    main()

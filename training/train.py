"""
train.py
--------
Phase 11 deliverable: fine-tune YOLO Nano on your custom classes
(phone, seatbelt, cigarette, food, drink).

Prerequisites (Phases 9-10, done by YOU - not automatable):
  1. Collect 300-3000 images per class (see README for diversity checklist:
     different people, lighting, camera angles, occlusions, etc.)
  2. Annotate with Roboflow or CVAT, export in YOLO format to:
       datasets/train/images, datasets/train/labels
       datasets/valid/images, datasets/valid/labels
       datasets/test/images,  datasets/test/labels
  3. Fill in datasets/data.yaml with your class names.

Usage:
    python training/train.py
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import config

try:
    from ultralytics import YOLO
except ImportError:
    raise SystemExit("Install ultralytics first: pip install ultralytics")

DATA_YAML = os.path.join(config.BASE_DIR, "datasets", "data.yaml")
EPOCHS = 100
IMG_SIZE = 640
BATCH_SIZE = 16   # lower this (e.g. 4-8) if you hit GPU out-of-memory errors


def main():
    if not os.path.exists(DATA_YAML):
        raise SystemExit(
            f"data.yaml not found at {DATA_YAML}. "
            f"Fill it in first (see datasets/data.yaml template)."
        )

    # Start from the pretrained COCO weights (transfer learning), not from scratch
    model = YOLO(config.YOLO_PRETRAINED_PATH if os.path.exists(config.YOLO_PRETRAINED_PATH) else "yolo11n.pt")

    model.train(
        data=DATA_YAML,
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        project=os.path.join(config.BASE_DIR, "training", "runs"),
        name="driverguardian_finetune",

        # Augmentation tuned for a fixed dash-mounted cabin camera that must
        # work day and night on a plain RGB sensor:
        hsv_h=0.015,   # slight hue jitter (default) - cabin colors don't vary much
        hsv_s=0.5,     # moderate saturation jitter - different clothing/skin tones
        hsv_v=0.6,     # wide brightness/value jitter - simulates day <-> night cabin lighting
        degrees=5.0,   # camera is fixed-mount, driver doesn't rotate much
        shear=2.0,
        translate=0.1,
        scale=0.4,     # driver distance from camera varies (seat position, phone distance)
        mosaic=0.8,
        mixup=0.1,
        fliplr=0.5,    # left/right-hand-drive symmetry
    )

    print("\nTraining complete.")
    print("Copy the resulting best.pt (in training/runs/.../weights/) to:")
    print(f"  {config.YOLO_FINETUNED_PATH}")


if __name__ == "__main__":
    main()

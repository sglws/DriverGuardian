"""
evaluate.py
-----------
Phase 12 deliverable: evaluate your fine-tuned model.
Reports precision, recall, mAP50, and confusion matrix.

Target: mAP50 > 90% if achievable with sufficient, diverse data.

Usage:
    python training/evaluate.py
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


def main():
    if not os.path.exists(config.YOLO_FINETUNED_PATH):
        raise SystemExit(
            f"No fine-tuned model found at {config.YOLO_FINETUNED_PATH}. "
            f"Run training/train.py first."
        )

    model = YOLO(config.YOLO_FINETUNED_PATH)
    metrics = model.val(data=DATA_YAML, split="test")

    print("\n--- Evaluation Results ---")
    print(f"mAP50:    {metrics.box.map50:.3f}")
    print(f"mAP50-95: {metrics.box.map:.3f}")
    print(f"Precision: {metrics.box.mp:.3f}")
    print(f"Recall:    {metrics.box.mr:.3f}")
    print("\nConfusion matrix and per-class plots saved under training/runs/.../")


if __name__ == "__main__":
    main()

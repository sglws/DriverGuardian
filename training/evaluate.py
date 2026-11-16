"""Test-set precision, recall and mAP of models/best.pt.

    python training/evaluate.py [path/to/data.yaml]     (default: dataset/data.yaml)
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import config  # noqa: E402

try:
    from ultralytics import YOLO
except ImportError:
    raise SystemExit("Install ultralytics first: pip install ultralytics")


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "dataset/data.yaml"
    if not os.path.exists(config.YOLO_MODEL_PATH):
        raise SystemExit(f"No model at {config.YOLO_MODEL_PATH} - run training/train.py first.")
    metrics = YOLO(config.YOLO_MODEL_PATH).val(data=data, split="test")
    print(f"\nmAP50 {metrics.box.map50:.3f}  mAP50-95 {metrics.box.map:.3f}  "
          f"precision {metrics.box.mp:.3f}  recall {metrics.box.mr:.3f}")


if __name__ == "__main__":
    main()

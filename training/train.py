"""Train the object detector (Drinking, Eating, Phone, Seatbelt, Smoking) on a GPU.

    python training/train.py [path/to/data.yaml]     (default: dataset/data.yaml, a Roboflow export)

After training it prints the per-class test results and the best confidence of each
class (starting values for YOLO_CLASS_CONF_THRESHOLDS). Copy best.pt to models/, then
run training/export.py.
"""

import sys
from pathlib import Path

import yaml
from ultralytics import YOLO

_args = [a for a in sys.argv[1:] if a.endswith((".yaml", ".yml"))]   # Jupyter adds its own arguments
DATA = Path(_args[0] if _args else "dataset/data.yaml")
MODEL = "yolo26n.pt"
NAME = "dms_v2_" + MODEL.split(".")[0]


def check_dataset(data_yaml: Path):
    """Stops with a clear message when a split folder is missing (Roboflow often writes '../')."""
    if not data_yaml.exists():
        sys.exit(f"No {data_yaml} - run from the folder that contains 'dataset', or pass the path.")
    cfg = yaml.safe_load(data_yaml.read_text())
    root = Path(cfg.get("path") or data_yaml.parent)
    for split in ("train", "val", "test"):
        images = root / cfg[split]
        if not images.is_dir():
            sys.exit(f"{split}: folder {images} not found. Check that the export was unzipped into "
                     f"{root}, and that {data_yaml.name} says {split}: "
                     f"{'valid' if split == 'val' else split}/images (Roboflow often writes '../' in front)")
        print(f"{split:5s} {len(list(images.iterdir())):5d} images  ({images})")


def main():
    check_dataset(DATA)

    model = YOLO(MODEL)
    model.train(
        data=str(DATA), name=NAME,
        epochs=150,
        patience=20,         
        cos_lr=True,
        close_mosaic=20,       # whole images at the end help the long, thin seatbelt
        imgsz=640,
        batch=-1,
        workers=4,
        seed=0, deterministic=True,
        hsv_h=0.015, hsv_s=0.7, hsv_v=0.5,        # changing cabin light; no upside-down flips
        degrees=5.0, translate=0.1, scale=0.4,
        fliplr=0.5, flipud=0.0,
        mosaic=1.0,
        mixup=0.05,
        plots=True, verbose=True,
    )

    best_pt = Path(model.trainer.save_dir) / "weights" / "best.pt"
    m = YOLO(best_pt).val(data=str(DATA), split="test", imgsz=640, plots=True, name=NAME + "_test")
    px, f1 = m.box.curves_results[1][:2]
    print(f"\nTEST  mAP50 {m.box.map50:.3f}   mAP50-95 {m.box.map:.3f}\n")
    print(f"{'class':10s} {'precision':>9s} {'recall':>7s} {'mAP50':>6s} {'mAP50-95':>9s} {'best conf':>10s}")
    for i, c in enumerate(m.box.ap_class_index):
        p, r, ap50, ap = m.box.class_result(i)
        print(f"{m.names[c]:10s} {p:9.3f} {r:7.3f} {ap50:6.3f} {ap:9.3f} {float(px[f1[i].argmax()]):10.2f}")
    print(f"\nModel: {best_pt}\n"
          "Thresholds for app/config.py: Phone -> phone, Eating/Drinking -> consumption (take the higher),\n"
          "Smoking -> cigarette, Seatbelt -> seatbelt. Start there, then check on the Pi.")


if __name__ == "__main__":
    main()

"""
train_v2.py
-----------
Retrain the DriverGuardian object detector (Drinking, Eating, Phone, Seatbelt,
Smoking) on a local GPU, from a Roboflow export in the "dataset" folder:

    python training/train_v2.py                         # dataset/data.yaml
    python training/train_v2.py path/to/data.yaml       # another export

Changes from the 22 Oct run (yolo26n, 120 epochs, mAP50 0.865, mAP50-95 0.565):
- Early stopping never triggered: patience counts epochs without a new best
  "fitness", which is mostly mAP50-95, and mAP50-95 was still creeping up at
  epoch 120. So: 150 epochs with a cosine learning rate for a clean finish.
- The seatbelt (77 % found, most background false detections) is long and thin
  and gets cut up by mosaic: mosaic stops 20 epochs before the end, and a light
  mixup adds background variety.
- Early stopping is off: close_mosaic and cos_lr count from the planned last
  epoch, so a run stopped early would never get its no-mosaic epochs. best.pt
  still keeps the best epoch.
- After training: per-class results on the test set, and the confidence with
  the best F1 for each class - starting values for YOLO_CLASS_CONF_THRESHOLDS
  in app/config.py.
Image size stays 640, the size the app runs the model at.
"""

import sys
from pathlib import Path

import yaml
from ultralytics import YOLO

# A command-line .yaml path if given; Jupyter puts its own kernel arguments in sys.argv, so only
# accept a .yaml file from there.
_args = [a for a in sys.argv[1:] if a.endswith((".yaml", ".yml"))]
DATA = Path(_args[0] if _args else "dataset/data.yaml")
MODEL = "yolo26n.pt"      # "yolo26s.pt": more accurate but 2-3x slower on the Pi -
                          # compare both with tools/compare_yolo_models.py before switching
NAME = "dms_v2_" + MODEL.split(".")[0]


def check_dataset(data_yaml: Path):
    """Roboflow exports often point to "../train/images", which is wrong once the
    folder is moved: stop with a clear message instead of a confusing error."""
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
        patience=150,         # = epochs: no early stop, so the last 20 no-mosaic epochs always run
        cos_lr=True,          # learning rate falls smoothly to the end
        close_mosaic=20,      # last 20 epochs on whole images (helps the long seatbelt)
        imgsz=640,            # same size as the app
        batch=-1,             # largest batch that fits the GPU (16 if not on CUDA)
        workers=4,
        seed=0, deterministic=True,
        # augmentation: a fixed, upright camera with changing cabin light
        hsv_h=0.015, hsv_s=0.7, hsv_v=0.5,
        degrees=5.0, translate=0.1, scale=0.4,
        fliplr=0.5, flipud=0.0,
        mosaic=1.0,
        mixup=0.05,           # light image blending: more background, fewer false detections
        plots=True, verbose=True,
    )

    # Test set: per-class results and the confidence with the best F1 per class
    best_pt = Path(model.trainer.save_dir) / "weights" / "best.pt"
    m = YOLO(best_pt).val(data=str(DATA), split="test", imgsz=640, plots=True, name=NAME + "_test")
    px, f1 = m.box.curves_results[1][:2]          # [confidence axis, F1 per class]
    print(f"\nTEST  mAP50 {m.box.map50:.3f}   mAP50-95 {m.box.map:.3f}\n")
    print(f"{'class':10s} {'precision':>9s} {'recall':>7s} {'mAP50':>6s} {'mAP50-95':>9s} {'best conf':>10s}")
    for i, c in enumerate(m.box.ap_class_index):
        p, r, ap50, ap = m.box.class_result(i)
        print(f"{m.names[c]:10s} {p:9.3f} {r:7.3f} {ap50:6.3f} {ap:9.3f} {float(px[f1[i].argmax()]):10.2f}")
    print(f"\nModel: {best_pt}\n"
          "Thresholds for app/config.py: Phone -> phone, Eating/Drinking -> consumption (take the higher),\n"
          "Smoking -> cigarette, Seatbelt -> seatbelt. Start there, then check on the Pi.")


if __name__ == "__main__":     # needed for the data-loading workers on Windows
    main()

#!/usr/bin/env python3
"""Train a YOLOv8-cls tile classifier for BioScan.

Uses the Ultralytics classification API to fine-tune a pretrained model
on the BioScan dataset prepared by scripts/prepare_dataset.py.

Quick test (tiny sample, 2 epochs):
    python scripts/train_classifier.py --epochs 2 --imgsz 224 --data data/classifier_dataset

Full training run:
    python scripts/train_classifier.py --epochs 50 --imgsz 224 --data data/classifier_dataset \\
        --model yolov8n-cls.pt --batch 32 --patience 10

Usage:
    python scripts/train_classifier.py [OPTIONS]
"""

import argparse
import sys
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train YOLOv8-cls for BioScan tile classification"
    )
    parser.add_argument(
        "--model", type=str, default="yolov8n-cls.pt",
        help="Pretrained model to fine-tune (default: yolov8n-cls.pt)"
    )
    parser.add_argument(
        "--data", type=str, default="data/classifier_dataset",
        help="Path to dataset root with train/ and val/ subdirectories"
    )
    parser.add_argument(
        "--epochs", type=int, default=50,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--imgsz", type=int, default=224,
        help="Input image size (matches tile size)"
    )
    parser.add_argument(
        "--batch", type=int, default=32,
        help="Batch size"
    )
    parser.add_argument(
        "--patience", type=int, default=10,
        help="Early stopping patience (0 to disable)"
    )
    parser.add_argument(
        "--device", type=str, default="cpu",
        help="Device: 'cpu', '0', '0,1', etc."
    )
    parser.add_argument(
        "--project", type=str, default="runs/classify",
        help="Project directory for saving results"
    )
    parser.add_argument(
        "--name", type=str, default="bioscan_tile_cls",
        help="Experiment name"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility"
    )
    args = parser.parse_args()

    data_dir = Path(args.data)
    train_dir = data_dir / "train"
    val_dir = data_dir / "val"

    if not train_dir.is_dir():
        print(f"ERROR: Training directory not found: {train_dir}")
        print("  Run scripts/prepare_dataset.py first.")
        sys.exit(1)

    if not val_dir.is_dir():
        print(f"ERROR: Validation directory not found: {val_dir}")
        sys.exit(1)

    # Count classes and images
    train_classes = sorted([d.name for d in train_dir.iterdir() if d.is_dir()])
    val_classes = sorted([d.name for d in val_dir.iterdir() if d.is_dir()])
    n_train = sum(len(list((train_dir / c).glob("*"))) for c in train_classes)
    n_val = sum(len(list((val_dir / c).glob("*"))) for c in val_classes)

    print("=" * 60)
    print("BioScan Tile Classifier Training")
    print("=" * 60)
    print(f"  Model:      {args.model}")
    print(f"  Data:       {data_dir}")
    print(f"  Train:      {n_train} images across {len(train_classes)} classes")
    print(f"  Val:        {n_val} images across {len(val_classes)} classes")
    print(f"  Classes:    {train_classes}")
    print(f"  Epochs:     {args.epochs}")
    print(f"  Image size: {args.imgsz}")
    print(f"  Batch size: {args.batch}")
    print(f"  Device:     {args.device}")
    print(f"  Seed:       {args.seed}")
    print("=" * 60)

    if n_train == 0:
        print("ERROR: No training images found. Run the remap and prepare scripts first.")
        sys.exit(1)

    # Load model
    model = YOLO(args.model)

    # Train
    results = model.train(
        data=str(data_dir),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=args.patience,
        device=args.device,
        project=args.project,
        name=args.name,
        seed=args.seed,
        verbose=True,
        # Augmentation (reasonable defaults for waste on belt)
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.3,
        degrees=15.0,
        flipud=0.3,
        fliplr=0.5,
        scale=0.3,
    )

    # Print final metrics
    print("\n" + "=" * 60)
    print("Training Complete")
    print("=" * 60)
    print(f"  Best model saved to: {results.save_dir}")

    # Copy best weights to models/ for the pipeline
    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    target_weights = Path("models") / "tile_classifier_best.pt"
    target_weights.parent.mkdir(parents=True, exist_ok=True)

    if best_weights.exists():
        import shutil
        shutil.copy2(best_weights, target_weights)
        print(f"  Weights copied to: {target_weights}")
    else:
        print(f"  WARNING: Best weights not found at {best_weights}")

    print("\nTo use this model in the pipeline, set the model path in your config.")


if __name__ == "__main__":
    main()

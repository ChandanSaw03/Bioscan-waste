#!/usr/bin/env python3
"""Prepare the combined BioScan classification dataset for YOLOv8-cls training.

Reads remapped images from multiple sources and assembles them into the
Ultralytics ImageFolder layout:

    data/classifier_dataset/
        train/
            food_organic/
            agri_residue/
            ...
        val/
            ...

Split is done BY SOURCE (not randomly) to avoid data leakage:
  - Garbage V2   → train
  - RealWaste    → val  (different domain = harder, more honest evaluation)
  - data/custom/ → train (user-supplied food/agri images)

Usage:
    python scripts/prepare_dataset.py
    python scripts/prepare_dataset.py --max-per-class 10   # tiny test split
"""

import argparse
import shutil
import sys
from pathlib import Path

import yaml


REMAPPED_SOURCES = {
    "garbage_v2": Path("data/remapped/garbage_v2"),
    "realwaste":  Path("data/remapped/realwaste"),
}
CUSTOM_DIR = Path("data/custom")
OUTPUT_DIR = Path("data/classifier_dataset")

# Split assignment by source
SOURCE_SPLIT = {
    "garbage_v2": "train",
    "realwaste":  "val",
    "custom":     "train",
}


def load_energy_classes(config_path: str = "config/classes.yaml") -> list[str]:
    """Load the list of 7 energy class names."""
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    return list(cfg["energy_classes"].values())


def copy_source(
    source_name: str,
    source_dir: Path,
    output_dir: Path,
    split: str,
    energy_classes: list[str],
    max_per_class: int | None = None,
) -> dict[str, int]:
    """Copy images from a remapped source into the dataset split."""
    counts: dict[str, int] = {}

    if not source_dir.is_dir():
        print(f"  SKIP: {source_dir} not found")
        return counts

    for cls_dir in sorted(source_dir.iterdir()):
        if not cls_dir.is_dir():
            continue
        cls_name = cls_dir.name

        # Skip hazard directories and classes not in our taxonomy
        if cls_name.startswith("_hazard"):
            print(f"  SKIP hazard: {cls_name}")
            continue
        if cls_name not in energy_classes:
            print(f"  SKIP unknown class: {cls_name}")
            continue

        dst_dir = output_dir / split / cls_name
        dst_dir.mkdir(parents=True, exist_ok=True)

        images = sorted(cls_dir.glob("*"))
        if max_per_class is not None:
            images = images[:max_per_class]

        copied = 0
        for img_path in images:
            if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                continue
            dst_path = dst_dir / img_path.name
            if not dst_path.exists():
                shutil.copy2(img_path, dst_path)
            copied += 1

        counts[cls_name] = counts.get(cls_name, 0) + copied

    return counts


def print_summary(split_counts: dict[str, dict[str, int]]) -> None:
    """Print a summary table of images per class per split."""
    all_classes = sorted(
        set(cls for counts in split_counts.values() for cls in counts)
    )
    print(f"\n{'Class':20s} {'train':>8s} {'val':>8s} {'test':>8s} {'total':>8s}")
    print("-" * 56)
    for cls in all_classes:
        train = split_counts.get("train", {}).get(cls, 0)
        val = split_counts.get("val", {}).get(cls, 0)
        test = split_counts.get("test", {}).get(cls, 0)
        total = train + val + test
        print(f"  {cls:20s} {train:>6d} {val:>8d} {test:>8d} {total:>8d}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare BioScan classifier dataset")
    parser.add_argument("--config", type=str, default="config/classes.yaml")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR))
    parser.add_argument("--max-per-class", type=int, default=None,
                        help="Max images per source class per source (for quick testing)")
    args = parser.parse_args()

    output = Path(args.output)
    energy_classes = load_energy_classes(args.config)
    print(f"Energy classes: {energy_classes}")
    print(f"Output directory: {output}")
    print()

    split_counts: dict[str, dict[str, int]] = {}

    # Process each remapped source
    for source_name, source_dir in REMAPPED_SOURCES.items():
        split = SOURCE_SPLIT[source_name]
        print(f"Processing {source_name} → {split}")
        counts = copy_source(
            source_name, source_dir, output, split, energy_classes,
            max_per_class=args.max_per_class,
        )
        if split not in split_counts:
            split_counts[split] = {}
        for cls, n in counts.items():
            split_counts[split][cls] = split_counts[split].get(cls, 0) + n

    # Process custom data
    if CUSTOM_DIR.is_dir():
        split = SOURCE_SPLIT["custom"]
        print(f"Processing custom → {split}")
        counts = copy_source(
            "custom", CUSTOM_DIR, output, split, energy_classes,
            max_per_class=args.max_per_class,
        )
        for cls, n in counts.items():
            split_counts[split][cls] = split_counts[split].get(cls, 0) + n
    else:
        print(f"  NOTE: {CUSTOM_DIR} not found. Create it with food/agri images.")

    # Ensure all classes exist in all splits (empty dirs are fine for Ultralytics)
    for split in ["train", "val"]:
        for cls in energy_classes:
            (output / split / cls).mkdir(parents=True, exist_ok=True)

    print_summary(split_counts)

    # Write a dataset.yaml for reference
    dataset_yaml = output / "dataset.yaml"
    ds_cfg = {
        "path": str(output.resolve()),
        "train": "train",
        "val": "val",
        "nc": len(energy_classes),
        "names": energy_classes,
    }
    with open(dataset_yaml, "w") as f:
        yaml.dump(ds_cfg, f, default_flow_style=False)
    print(f"\nDataset config written to: {dataset_yaml}")


if __name__ == "__main__":
    main()

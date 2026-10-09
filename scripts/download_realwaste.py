#!/usr/bin/env python3
"""Download and remap RealWaste dataset to BioScan 7-class taxonomy.

RealWaste is available on Kaggle:
  https://www.kaggle.com/datasets/joebeachcapital/realwaste

Since Kaggle requires authentication, this script supports two modes:
  1. --kaggle : Uses the Kaggle API (requires ~/.kaggle/kaggle.json)
  2. --manual : Assumes the dataset is already extracted to data/raw/realwaste/

After obtaining the raw data, images are remapped to BioScan classes.

Usage:
    # Option 1: Download via Kaggle API
    python scripts/download_realwaste.py --kaggle

    # Option 2: Manual (extract the Kaggle zip to data/raw/realwaste/ first)
    python scripts/download_realwaste.py --manual

    # Quick test with 5 images per class
    python scripts/download_realwaste.py --manual --max-per-class 5
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


RAW_DIR = Path("data/raw/realwaste")
REMAP_DST = Path("data/remapped/realwaste")
KAGGLE_DATASET = "joebeachcapital/realwaste"


def load_remap_table(config_path: str = "config/classes.yaml") -> dict[str, str]:
    """Load the RealWaste → BioScan remap table from config."""
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    return cfg["remap_realwaste"]


def download_kaggle(raw_dir: Path) -> None:
    """Download RealWaste via the Kaggle CLI."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {KAGGLE_DATASET} via Kaggle API...")
    try:
        subprocess.run(
            [
                "kaggle", "datasets", "download",
                "-d", KAGGLE_DATASET,
                "-p", str(raw_dir),
                "--unzip",
            ],
            check=True,
        )
        print(f"Downloaded to {raw_dir}")
    except FileNotFoundError:
        print("ERROR: 'kaggle' CLI not found. Install with: pip install kaggle")
        print("       Then place your API key in ~/.kaggle/kaggle.json")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Kaggle download failed: {e}")
        sys.exit(1)


def find_image_root(raw_dir: Path) -> Path:
    """Find the directory containing class subdirectories.

    RealWaste extracts with varying nesting. We look for the level
    that contains known class names.
    """
    known_classes = {"Cardboard", "Food Organics", "Glass", "Metal", "Paper", "Plastic"}

    # Check raw_dir itself
    children = {d.name for d in raw_dir.iterdir() if d.is_dir()}
    if known_classes & children:
        return raw_dir

    # Check one level deeper
    for child in raw_dir.iterdir():
        if child.is_dir():
            grandchildren = {d.name for d in child.iterdir() if d.is_dir()}
            if known_classes & grandchildren:
                return child

    # Check two levels deep
    for child in raw_dir.iterdir():
        if child.is_dir():
            for grandchild in child.iterdir():
                if grandchild.is_dir():
                    ggchildren = {d.name for d in grandchild.iterdir() if d.is_dir()}
                    if known_classes & ggchildren:
                        return grandchild

    print(f"ERROR: Could not find RealWaste class directories under {raw_dir}")
    print(f"  Expected subdirectories like: {known_classes}")
    print(f"  Found: {children}")
    sys.exit(1)


def remap_dataset(
    src_dir: Path,
    dst_dir: Path,
    remap: dict[str, str],
    max_per_class: int | None = None,
) -> dict[str, int]:
    """Copy and remap images from src_dir to dst_dir."""
    counts: dict[str, int] = {}

    for src_class, bioscan_class in remap.items():
        src_class_dir = src_dir / src_class
        if not src_class_dir.is_dir():
            print(f"  SKIP: {src_class_dir} not found")
            continue

        dst_class_dir = dst_dir / bioscan_class
        dst_class_dir.mkdir(parents=True, exist_ok=True)

        images = sorted(src_class_dir.glob("*"))
        if max_per_class is not None:
            images = images[:max_per_class]

        copied = 0
        for img_path in images:
            if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                continue
            dst_name = f"rw_{img_path.name}"
            dst_path = dst_class_dir / dst_name
            if not dst_path.exists():
                shutil.copy2(img_path, dst_path)
            copied += 1

        counts[bioscan_class] = counts.get(bioscan_class, 0) + copied
        print(f"  {src_class:25s} → {bioscan_class:20s}: {copied} images")

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and remap RealWaste")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--kaggle", action="store_true",
                       help="Download via Kaggle API")
    group.add_argument("--manual", action="store_true",
                       help="Assume raw data already in data/raw/realwaste/")
    parser.add_argument("--config", type=str, default="config/classes.yaml")
    parser.add_argument("--max-per-class", type=int, default=None,
                        help="Max images per source class (for quick testing)")
    args = parser.parse_args()

    if args.kaggle:
        download_kaggle(RAW_DIR)

    if not RAW_DIR.is_dir():
        print(f"ERROR: Raw directory not found: {RAW_DIR}")
        print("  Download RealWaste from Kaggle and extract to data/raw/realwaste/")
        sys.exit(1)

    image_root = find_image_root(RAW_DIR)
    print(f"Found image root: {image_root}")

    remap = load_remap_table(args.config)
    print(f"Remapping RealWaste: {image_root} → {REMAP_DST}")
    print()

    counts = remap_dataset(image_root, REMAP_DST, remap, max_per_class=args.max_per_class)

    print("\n--- Summary ---")
    total = 0
    for cls, n in sorted(counts.items()):
        print(f"  {cls:20s}: {n:5d}")
        total += n
    print(f"  {'TOTAL':20s}: {total:5d}")


if __name__ == "__main__":
    main()

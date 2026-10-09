#!/usr/bin/env python3
"""Remap Garbage Dataset V2 classes to BioScan 7-class taxonomy.

Reads images from data/original/<source_class>/ and copies them into
data/remapped/garbage_v2/<bioscan_class>/.

Hazard items (battery) are placed in data/remapped/garbage_v2/_hazard_battery/
for flagging purposes but are excluded from the energy class set.

Usage:
    python scripts/remap_garbage_v2.py [--src data/original] [--dst data/remapped/garbage_v2]
"""

import argparse
import shutil
import sys
from pathlib import Path

import yaml


def load_remap_table(config_path: str = "config/classes.yaml") -> dict[str, str]:
    """Load the Garbage V2 → BioScan remap table from config."""
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    return cfg["remap_garbage_v2"]


def remap_dataset(
    src_dir: Path,
    dst_dir: Path,
    remap: dict[str, str],
    max_per_class: int | None = None,
) -> dict[str, int]:
    """Copy and remap images from src_dir to dst_dir.

    Args:
        src_dir: Root of Garbage V2 (contains class subdirectories).
        dst_dir: Output root (will contain BioScan class subdirectories).
        remap: Mapping from source class name → BioScan class name.
        max_per_class: If set, copy at most this many images per source class
                       (useful for quick testing).

    Returns:
        Dictionary of {bioscan_class: count} with images copied.
    """
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
            # Prefix with source class to avoid filename collisions
            dst_name = f"gv2_{src_class}_{img_path.name}"
            dst_path = dst_class_dir / dst_name
            if not dst_path.exists():
                shutil.copy2(img_path, dst_path)
            copied += 1

        counts[bioscan_class] = counts.get(bioscan_class, 0) + copied
        print(f"  {src_class:20s} → {bioscan_class:20s}: {copied} images")

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Remap Garbage V2 → BioScan classes")
    parser.add_argument("--src", type=str, default="data/original",
                        help="Path to Garbage V2 root directory")
    parser.add_argument("--dst", type=str, default="data/remapped/garbage_v2",
                        help="Output directory for remapped images")
    parser.add_argument("--config", type=str, default="config/classes.yaml",
                        help="Path to classes.yaml with remap table")
    parser.add_argument("--max-per-class", type=int, default=None,
                        help="Max images per source class (for quick testing)")
    args = parser.parse_args()

    src_dir = Path(args.src)
    dst_dir = Path(args.dst)

    if not src_dir.is_dir():
        print(f"ERROR: Source directory not found: {src_dir}")
        sys.exit(1)

    remap = load_remap_table(args.config)
    print(f"Remapping Garbage V2: {src_dir} → {dst_dir}")
    print(f"Remap table: {remap}")
    print()

    counts = remap_dataset(src_dir, dst_dir, remap, max_per_class=args.max_per_class)

    print("\n--- Summary ---")
    total = 0
    for cls, n in sorted(counts.items()):
        print(f"  {cls:20s}: {n:5d}")
        total += n
    print(f"  {'TOTAL':20s}: {total:5d}")


if __name__ == "__main__":
    main()

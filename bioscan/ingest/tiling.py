"""Grid tiling for patch-based classification.

Splits a frame (or belt ROI crop) into a grid of tiles for classification.
Each tile is independently classified, and the results are aggregated into
a composition vector.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from bioscan.config_loader import GridConfig


@dataclass
class Tile:
    """A single tile extracted from a frame grid."""

    row: int
    col: int
    image: np.ndarray          # H×W×C, uint8
    x: int                     # top-left x in source frame
    y: int                     # top-left y in source frame


def tile_frame(
    frame: np.ndarray,
    grid_cfg: GridConfig,
) -> list[Tile]:
    """Split a frame into non-overlapping (or strided) tiles.

    Args:
        frame: BGR image as H×W×3 uint8 ndarray.
        grid_cfg: Grid configuration (tile_size, stride, min_belt_coverage).

    Returns:
        List of Tile objects. Edge tiles smaller than tile_size are padded
        with zeros but only included if they have enough real pixels
        (≥ min_belt_coverage fraction of tile area).
    """
    h, w = frame.shape[:2]
    tile_size = grid_cfg.tile_size
    stride = grid_cfg.stride
    min_coverage = grid_cfg.min_belt_coverage
    min_pixels = int(tile_size * tile_size * min_coverage)

    tiles: list[Tile] = []
    row_idx = 0

    for y in range(0, h, stride):
        col_idx = 0
        for x in range(0, w, stride):
            # Extract the tile region
            y_end = min(y + tile_size, h)
            x_end = min(x + tile_size, w)
            patch = frame[y:y_end, x:x_end]

            real_pixels = patch.shape[0] * patch.shape[1]
            if real_pixels < min_pixels:
                col_idx += 1
                continue

            # Pad if the tile is at an edge
            if patch.shape[0] < tile_size or patch.shape[1] < tile_size:
                padded = np.zeros((tile_size, tile_size, 3), dtype=np.uint8)
                padded[:patch.shape[0], :patch.shape[1]] = patch
                patch = padded

            tiles.append(Tile(row=row_idx, col=col_idx, image=patch, x=x, y=y))
            col_idx += 1

        row_idx += 1

    return tiles


@dataclass
class TileClassification:
    """Classification result for a single tile."""

    tile: Tile
    class_name: str
    confidence: float
    hazard_flag: str | None = None   # e.g. "battery" if detected


@dataclass
class FrameComposition:
    """Composition vector derived from classifying all tiles in a frame.

    tile_shares: fraction of tiles classified as each class (0–1, sums to 1).
    n_tiles: total number of classified tiles.
    hazard_flags: set of any hazard items detected.
    avg_confidence: mean classification confidence across tiles.
    """

    tile_shares: dict[str, float]
    n_tiles: int
    hazard_flags: set[str]
    avg_confidence: float


def aggregate_tile_classifications(
    classifications: list[TileClassification],
    energy_classes: list[str],
) -> FrameComposition:
    """Aggregate per-tile classifications into a frame-level composition.

    Args:
        classifications: Classification results for each tile.
        energy_classes: List of valid energy class names.

    Returns:
        FrameComposition with tile share fractions summing to 1.
    """
    if not classifications:
        return FrameComposition(
            tile_shares={cls: 0.0 for cls in energy_classes},
            n_tiles=0,
            hazard_flags=set(),
            avg_confidence=0.0,
        )

    counts: dict[str, int] = {cls: 0 for cls in energy_classes}
    hazards: set[str] = set()
    total_conf = 0.0
    n_energy_tiles = 0

    for tc in classifications:
        if tc.hazard_flag:
            hazards.add(tc.hazard_flag)
            continue  # hazard tiles excluded from composition shares

        if tc.class_name in counts:
            counts[tc.class_name] += 1
            total_conf += tc.confidence
            n_energy_tiles += 1

    total = max(n_energy_tiles, 1)
    tile_shares = {cls: count / total for cls, count in counts.items()}
    avg_conf = total_conf / total if n_energy_tiles > 0 else 0.0

    return FrameComposition(
        tile_shares=tile_shares,
        n_tiles=n_energy_tiles,
        hazard_flags=hazards,
        avg_confidence=avg_conf,
    )

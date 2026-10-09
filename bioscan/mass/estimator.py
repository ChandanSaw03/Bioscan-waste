"""Mass estimation from tile-share composition.

In the patch-based approach, composition is expressed as tile fractions,
not individual object masks. Mass is estimated by treating the total
visible belt area and distributing it across classes according to tile
shares, then applying per-class thickness and density factors.

Formula per class c:
    area_cm2_c  = total_tile_area_cm2 × tile_share_c
    volume_cm3  = area_cm2_c × thickness_cm[c]
    mass_kg_c   = volume_cm3 × density_g_cm3[c] / 1000
"""

from __future__ import annotations

from bioscan.config_loader import BioScanConfig
from bioscan.ingest.tiling import FrameComposition


def estimate_mass_from_composition(
    composition: FrameComposition,
    config: BioScanConfig,
) -> dict[str, float]:
    """Estimate mass (kg) per class from a frame's tile composition.

    Args:
        composition: FrameComposition with tile_shares and n_tiles.
        config: BioScanConfig with waste_factors and cm2_per_pixel.

    Returns:
        Dictionary of {class_name: mass_kg}.
    """
    tile_area_px = config.grid.tile_size * config.grid.tile_size
    tile_area_cm2 = tile_area_px * config.cm2_per_pixel
    total_area_cm2 = tile_area_cm2 * composition.n_tiles

    mass_by_class: dict[str, float] = {}
    for cls in config.energy_classes:
        share = composition.tile_shares.get(cls, 0.0)
        factors = config.waste_factors[cls]

        area_cm2 = total_area_cm2 * share
        volume_cm3 = area_cm2 * factors.thickness_cm
        mass_kg = volume_cm3 * factors.density_g_cm3 / 1000.0

        mass_by_class[cls] = mass_kg

    return mass_by_class


def estimate_mass_single_class(
    area_cm2: float,
    thickness_cm: float,
    density_g_cm3: float,
) -> float:
    """Estimate mass (kg) from area, thickness, and density.

    This is the core calculation exposed for unit testing.

    Args:
        area_cm2: Visible area in cm².
        thickness_cm: Assumed layer thickness in cm.
        density_g_cm3: Effective bulk density in g/cm³.

    Returns:
        Estimated mass in kg.
    """
    volume_cm3 = area_cm2 * thickness_cm
    mass_kg = volume_cm3 * density_g_cm3 / 1000.0
    return mass_kg

"""Tests for the mass estimator."""

import pytest
from bioscan.mass.estimator import estimate_mass_single_class, estimate_mass_from_composition
from bioscan.config_loader import BioScanConfig, GridConfig, WasteClassFactors, UncertaintyConfig, ThresholdsConfig
from bioscan.ingest.tiling import FrameComposition

def test_estimate_mass_single_class() -> None:
    # area_cm2 = 100
    # thickness_cm = 4.0
    # -> volume_cm3 = 400
    # density_g_cm3 = 0.5
    # -> mass_g = 200 -> mass_kg = 0.2
    
    mass_kg = estimate_mass_single_class(area_cm2=100.0, thickness_cm=4.0, density_g_cm3=0.5)
    assert mass_kg == pytest.approx(0.2)

def test_estimate_mass_from_composition() -> None:
    classes = ["food_organic", "plastic"]
    groups = {"organic": ["food_organic"], "combustible": ["plastic"], "inert": []}
    factors = {
        "food_organic": WasteClassFactors(0.6, 4.0, 0.7, 0.9, 0.45, 4.0),
        "plastic": WasteClassFactors(0.08, 3.0, 0.02, 0.0, 0.0, 32.0),
    }
    config = BioScanConfig(
        energy_classes=classes,
        groups=groups,
        hazard_flags=[],
        waste_factors=factors,
        methane_lhv_kwh_per_nm3=9.97,
        chp_efficiency=0.38,
        wte_efficiency=0.22,
        uncertainty=UncertaintyConfig(0.25, 0.1, 0.2, 0.15),
        thresholds=ThresholdsConfig(0.35, 0.7, 0.1, 0.4),
        cm2_per_pixel=0.05,
        grid=GridConfig(224, 224, 0.3)
    )
    
    # 224*224 = 50176 px. * 0.05 = 2508.8 cm2 per tile.
    # 10 tiles = 25088 cm2 total area
    comp = FrameComposition(
        tile_shares={"food_organic": 0.8, "plastic": 0.2},
        n_tiles=10,
        hazard_flags=set(),
        avg_confidence=0.9
    )
    
    masses = estimate_mass_from_composition(comp, config)
    
    # 8 tiles food = 20070.4 cm2
    # vol = 20070.4 * 4.0 = 80281.6 cm3
    # mass = 80281.6 * 0.6 / 1000 = 48.16896 kg
    assert masses["food_organic"] == pytest.approx(48.16896)
    
    # 2 tiles plastic = 5017.6 cm2
    # vol = 5017.6 * 3.0 = 15052.8 cm3
    # mass = 15052.8 * 0.08 / 1000 = 1.204224 kg
    assert masses["plastic"] == pytest.approx(1.204224)


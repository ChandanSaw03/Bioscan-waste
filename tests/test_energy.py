"""Tests for the energy engine and recommendation logic."""

import pytest
from bioscan.energy.engine import compute_biogas, compute_incineration, recommend, EnergyEngine
from bioscan.batch.aggregator import Batch
from bioscan.config_loader import BioScanConfig, GridConfig, WasteClassFactors, UncertaintyConfig, ThresholdsConfig
from datetime import datetime

def make_test_config() -> BioScanConfig:
    classes = ["food_organic", "plastic"]
    groups = {"organic": ["food_organic"], "combustible": ["plastic"], "inert": []}
    factors = {
        "food_organic": WasteClassFactors(0.6, 4.0, 0.7, 0.9, 0.45, 4.0),
        "plastic": WasteClassFactors(0.08, 3.0, 0.02, 0.0, 0.0, 32.0),
    }
    return BioScanConfig(
        energy_classes=classes,
        groups=groups,
        hazard_flags=[],
        waste_factors=factors,
        methane_lhv_kwh_per_nm3=10.0,  # simplifying to 10 for hand-calc
        chp_efficiency=0.40,
        wte_efficiency=0.20,
        uncertainty=UncertaintyConfig(0.25, 0.1, 0.2, 0.15),
        thresholds=ThresholdsConfig(0.35, 0.7, 0.1, 0.4),
        cm2_per_pixel=0.05,
        grid=GridConfig(224, 224, 0.3)
    )


def test_compute_biogas() -> None:
    cfg = make_test_config()
    
    # 10 kg food_organic
    # moisture 0.7 -> 3 kg dry
    # vs 0.9 -> 2.7 kg VS
    # bmp 0.45 -> 1.215 Nm3 CH4
    # thermal kWh = 1.215 * 10.0 = 12.15
    # elec kWh = 12.15 * 0.40 = 4.86
    
    masses = {"food_organic": 10.0, "plastic": 2.0} # plastic has 0 bmp
    
    ch4, th, elec = compute_biogas(masses, cfg)
    
    assert ch4 == pytest.approx(1.215)
    assert th == pytest.approx(12.15)
    assert elec == pytest.approx(4.86)


def test_compute_incineration() -> None:
    cfg = make_test_config()
    
    # 10 kg food_organic, LHV = 4 -> 40 MJ
    # 2 kg plastic, LHV = 32 -> 64 MJ
    # Total MJ = 104
    # thermal kWh = 104 / 3.6 = 28.888...
    # elec kWh = 28.888... * 0.20 = 5.777...
    
    masses = {"food_organic": 10.0, "plastic": 2.0}
    
    mj, th, elec = compute_incineration(masses, cfg)
    
    assert mj == pytest.approx(104.0)
    assert th == pytest.approx(104.0 / 3.6)
    assert elec == pytest.approx((104.0 / 3.6) * 0.20)


def test_recommend_logic() -> None:
    cfg = make_test_config()
    
    def make_batch(food: float, plastic: float, inert: float=0) -> Batch:
        return Batch(
            batch_id="test",
            t_start=datetime.now(),
            t_end=datetime.now(),
            mass_by_class={"food_organic": food, "plastic": plastic, "glass_inert": inert},
            n_frames=1,
        )

    # 1. Mostly inert -> Reject
    b1 = make_batch(food=1, plastic=1, inert=8)
    assert recommend(b1, 0, 0, cfg)[0] == "reject"
    
    # 2. High organic, low plastic -> Biogas
    # food=10, plastic=0.5 -> plastic_frac = 0.5/10.5 = 4.7% < 10%
    b2 = make_batch(food=10, plastic=0.5)
    assert recommend(b2, 10.0, 5.0, cfg)[0] == "biogas"
    
    # 3. High organic, but plastic too high -> Mixed
    # food=10, plastic=2 -> plastic_frac = 16.6% > 10%
    b3 = make_batch(food=10, plastic=2.0)
    assert recommend(b3, 10.0, 5.0, cfg)[0] == "mixed"

    # 4. Better WTE yield -> Incineration
    # food=2, plastic=10 -> plastic_frac 83%, WTE should naturally be much higher
    b4 = make_batch(food=2, plastic=10)
    assert recommend(b4, 1.0, 20.0, cfg)[0] == "incineration"

    # 5. Comparable yields but high organic -> Biogas
    # biogas is 4.0, wte is 4.5. elec_biogas_mid (4.0) >= elec_wte_mid * 0.8 (3.6) => Biogas!
    b5 = make_batch(food=10, plastic=1)
    assert recommend(b5, 4.0, 4.5, cfg)[0] == "biogas"


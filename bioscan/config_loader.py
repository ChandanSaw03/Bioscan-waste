"""Centralised config loading and validation for BioScan.

All config is loaded once and passed explicitly to modules.
No module reads YAML on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Data classes for typed config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WasteClassFactors:
    """Per-class physical and energy factors. Units in attribute names."""

    density_g_cm3: float
    thickness_cm: float
    moisture: float            # fraction 0–1
    vs_fraction: float         # fraction 0–1
    bmp_nm3_ch4_per_kg_vs: float
    lhv_mj_per_kg: float


@dataclass(frozen=True)
class UncertaintyConfig:
    """Relative / absolute uncertainty bands for the MVP bounding method."""

    mass_rel: float
    moisture_abs: float
    bmp_rel: float
    lhv_rel: float


@dataclass(frozen=True)
class ThresholdsConfig:
    """Thresholds for confidence filtering and recommendation logic."""

    min_confidence: float
    reject_inert_fraction: float
    digester_max_plastic_fraction: float
    min_organic_fraction_biogas: float


@dataclass(frozen=True)
class GridConfig:
    """Grid tiling parameters for patch-based classification."""

    tile_size: int
    stride: int
    min_belt_coverage: float


@dataclass(frozen=True)
class BioScanConfig:
    """Top-level configuration container for the entire pipeline."""

    # Class taxonomy
    energy_classes: list[str]
    groups: dict[str, list[str]]       # organic / combustible / inert
    hazard_flags: list[str]

    # Per-class factors
    waste_factors: dict[str, WasteClassFactors]

    # Energy engine
    methane_lhv_kwh_per_nm3: float
    chp_efficiency: float
    wte_efficiency: float
    uncertainty: UncertaintyConfig
    thresholds: ThresholdsConfig

    # Camera / ingestion
    cm2_per_pixel: float
    grid: GridConfig


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _validate_fraction(value: float, name: str) -> None:
    """Raise if value is not in [0, 1]."""
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} = {value} is outside [0, 1]")


def load_config(
    classes_path: str | Path = "config/classes.yaml",
    waste_factors_path: str | Path = "config/waste_factors.yaml",
    energy_path: str | Path = "config/energy.yaml",
    camera_path: str | Path = "config/camera.yaml",
) -> BioScanConfig:
    """Load and validate all config files into a single BioScanConfig.

    Fails fast with a descriptive message if any key is missing or invalid.
    """
    # --- classes.yaml ---
    with open(classes_path) as f:
        cls_cfg = yaml.safe_load(f)

    energy_classes = list(cls_cfg["energy_classes"].values())
    groups = cls_cfg["groups"]
    hazard_flags = cls_cfg.get("hazard_flags", [])

    # Verify groups cover all energy classes
    grouped = {c for g in groups.values() for c in g}
    if grouped != set(energy_classes):
        missing = set(energy_classes) - grouped
        extra = grouped - set(energy_classes)
        raise ValueError(
            f"Group coverage mismatch. Missing: {missing}, Extra: {extra}"
        )

    # --- waste_factors.yaml ---
    with open(waste_factors_path) as f:
        wf_raw = yaml.safe_load(f)

    waste_factors: dict[str, WasteClassFactors] = {}
    for cls in energy_classes:
        if cls not in wf_raw:
            raise ValueError(f"Missing waste factors for class: {cls}")
        d = wf_raw[cls]
        required = {
            "density_g_cm3", "thickness_cm", "moisture",
            "vs_fraction", "bmp_nm3_ch4_per_kg_vs", "lhv_mj_per_kg",
        }
        missing_keys = required - set(d.keys())
        if missing_keys:
            raise ValueError(f"Missing keys for {cls}: {missing_keys}")

        _validate_fraction(d["moisture"], f"{cls}.moisture")
        _validate_fraction(d["vs_fraction"], f"{cls}.vs_fraction")

        waste_factors[cls] = WasteClassFactors(
            density_g_cm3=float(d["density_g_cm3"]),
            thickness_cm=float(d["thickness_cm"]),
            moisture=float(d["moisture"]),
            vs_fraction=float(d["vs_fraction"]),
            bmp_nm3_ch4_per_kg_vs=float(d["bmp_nm3_ch4_per_kg_vs"]),
            lhv_mj_per_kg=float(d["lhv_mj_per_kg"]),
        )

    # --- energy.yaml ---
    with open(energy_path) as f:
        en_cfg = yaml.safe_load(f)

    unc = en_cfg["uncertainty"]
    uncertainty = UncertaintyConfig(
        mass_rel=float(unc["mass_rel"]),
        moisture_abs=float(unc["moisture_abs"]),
        bmp_rel=float(unc["bmp_rel"]),
        lhv_rel=float(unc["lhv_rel"]),
    )

    thr = en_cfg["thresholds"]
    thresholds = ThresholdsConfig(
        min_confidence=float(thr["min_confidence"]),
        reject_inert_fraction=float(thr["reject_inert_fraction"]),
        digester_max_plastic_fraction=float(thr["digester_max_plastic_fraction"]),
        min_organic_fraction_biogas=float(thr["min_organic_fraction_biogas"]),
    )

    # --- camera.yaml ---
    with open(camera_path) as f:
        cam_cfg = yaml.safe_load(f)

    grid_raw = cam_cfg.get("grid", {})
    grid = GridConfig(
        tile_size=int(grid_raw.get("tile_size", 224)),
        stride=int(grid_raw.get("stride", 224)),
        min_belt_coverage=float(grid_raw.get("min_belt_coverage", 0.3)),
    )

    return BioScanConfig(
        energy_classes=energy_classes,
        groups=groups,
        hazard_flags=hazard_flags,
        waste_factors=waste_factors,
        methane_lhv_kwh_per_nm3=float(en_cfg["methane_lhv_kwh_per_nm3"]),
        chp_efficiency=float(en_cfg["chp_efficiency"]),
        wte_efficiency=float(en_cfg["wte_efficiency"]),
        uncertainty=uncertainty,
        thresholds=thresholds,
        cm2_per_pixel=float(cam_cfg["cm2_per_pixel"]),
        grid=grid,
    )

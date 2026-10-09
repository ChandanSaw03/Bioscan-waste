"""Tests for the data pipeline: config loading, remap logic, and dataset preparation."""

from pathlib import Path

import yaml
import pytest


CONFIG_DIR = Path("config")


class TestConfigFiles:
    """Verify all config YAML files load and have required keys."""

    def test_classes_yaml_loads(self) -> None:
        """classes.yaml loads and contains the 7 energy classes."""
        with open(CONFIG_DIR / "classes.yaml") as f:
            cfg = yaml.safe_load(f)

        assert "energy_classes" in cfg
        classes = list(cfg["energy_classes"].values())
        assert len(classes) == 7
        expected = [
            "food_organic", "agri_residue", "paper_cardboard",
            "plastic", "textile", "metal", "glass_inert",
        ]
        assert classes == expected

    def test_classes_yaml_groups(self) -> None:
        """classes.yaml groups cover all 7 energy classes exactly."""
        with open(CONFIG_DIR / "classes.yaml") as f:
            cfg = yaml.safe_load(f)

        groups = cfg["groups"]
        all_grouped = []
        for group_classes in groups.values():
            all_grouped.extend(group_classes)

        energy_classes = set(cfg["energy_classes"].values())
        assert set(all_grouped) == energy_classes

    def test_classes_yaml_remap_tables(self) -> None:
        """Remap tables map to valid BioScan classes or hazard flags."""
        with open(CONFIG_DIR / "classes.yaml") as f:
            cfg = yaml.safe_load(f)

        energy_classes = set(cfg["energy_classes"].values())
        hazard_prefixes = {"_hazard_"}

        for table_key in ("remap_garbage_v2", "remap_realwaste"):
            remap = cfg[table_key]
            for src, dst in remap.items():
                is_hazard = any(dst.startswith(p) for p in hazard_prefixes)
                assert dst in energy_classes or is_hazard, (
                    f"{table_key}: '{src}' maps to '{dst}' which is neither "
                    f"an energy class nor a hazard flag"
                )

    def test_waste_factors_yaml_loads(self) -> None:
        """waste_factors.yaml has entries for all 7 energy classes with required keys."""
        with open(CONFIG_DIR / "waste_factors.yaml") as f:
            factors = yaml.safe_load(f)

        with open(CONFIG_DIR / "classes.yaml") as f:
            classes = list(yaml.safe_load(f)["energy_classes"].values())

        required_keys = {
            "density_g_cm3", "thickness_cm", "moisture",
            "vs_fraction", "bmp_nm3_ch4_per_kg_vs", "lhv_mj_per_kg",
        }

        for cls in classes:
            assert cls in factors, f"Missing waste factors for class: {cls}"
            for key in required_keys:
                assert key in factors[cls], f"Missing key '{key}' for class '{cls}'"
                val = factors[cls][key]
                assert isinstance(val, (int, float)), (
                    f"'{key}' for '{cls}' must be numeric, got {type(val)}"
                )

    def test_waste_factors_fractions_in_range(self) -> None:
        """Moisture and vs_fraction must be in [0, 1]."""
        with open(CONFIG_DIR / "waste_factors.yaml") as f:
            factors = yaml.safe_load(f)

        for cls, vals in factors.items():
            for frac_key in ("moisture", "vs_fraction"):
                v = vals[frac_key]
                assert 0.0 <= v <= 1.0, (
                    f"{cls}.{frac_key} = {v} is outside [0, 1]"
                )

    def test_energy_yaml_loads(self) -> None:
        """energy.yaml loads with all required keys."""
        with open(CONFIG_DIR / "energy.yaml") as f:
            cfg = yaml.safe_load(f)

        assert cfg["methane_lhv_kwh_per_nm3"] == pytest.approx(9.97)
        assert 0 < cfg["chp_efficiency"] < 1
        assert 0 < cfg["wte_efficiency"] < 1
        assert "uncertainty" in cfg
        assert "thresholds" in cfg

    def test_camera_yaml_loads(self) -> None:
        """camera.yaml loads with grid tiling config."""
        with open(CONFIG_DIR / "camera.yaml") as f:
            cfg = yaml.safe_load(f)

        assert "grid" in cfg
        assert cfg["grid"]["tile_size"] > 0
        assert cfg["grid"]["stride"] > 0
        assert cfg["fps_process"] > 0


class TestRemapLogic:
    """Test the remap script's core logic without requiring full datasets."""

    def test_garbage_v2_remap_covers_all_sources(self) -> None:
        """The remap table covers all 10 Garbage V2 source classes."""
        with open(CONFIG_DIR / "classes.yaml") as f:
            cfg = yaml.safe_load(f)

        expected_sources = {
            "biological", "cardboard", "paper", "plastic",
            "clothes", "shoes", "metal", "glass", "trash", "battery",
        }
        actual_sources = set(cfg["remap_garbage_v2"].keys())
        assert actual_sources == expected_sources

    def test_no_wood_class(self) -> None:
        """The 'wood' class must not exist (dropped per overrides)."""
        with open(CONFIG_DIR / "classes.yaml") as f:
            cfg = yaml.safe_load(f)

        classes = set(cfg["energy_classes"].values())
        assert "wood" not in classes

        with open(CONFIG_DIR / "waste_factors.yaml") as f:
            factors = yaml.safe_load(f)
        assert "wood" not in factors

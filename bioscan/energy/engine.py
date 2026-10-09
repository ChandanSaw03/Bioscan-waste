"""Energy engine: biogas and incineration pathways with uncertainty ranges.

Implements design.md §4 algorithms exactly:
  - §4.3 Biogas: dry → VS → CH₄ → kWh_thermal → kWh_electric
  - §4.4 Incineration: LHV → MJ → kWh_thermal → kWh_electric
  - §4.5 Uncertainty: low/mid/high bounding method
  - §4.6 Recommendation logic with reason strings

All factors are read from BioScanConfig. No hard-coded constants.
"""

from __future__ import annotations

from dataclasses import dataclass

from bioscan.batch.aggregator import Batch
from bioscan.config_loader import BioScanConfig


@dataclass(frozen=True)
class EnergyResult:
    """A three-point estimate: low / mid / high. Units in the field name."""

    low: float
    mid: float
    high: float


@dataclass(frozen=True)
class BatchEnergy:
    """Full energy evaluation for a batch. Matches design.md §2."""

    ch4_nm3: EnergyResult
    thermal_biogas_kwh: EnergyResult
    elec_biogas_kwh: EnergyResult
    heat_mj: EnergyResult
    thermal_wte_kwh: EnergyResult
    elec_wte_kwh: EnergyResult
    recommendation: str     # biogas | incineration | mixed | reject
    reason: str
    hazard_flags: set[str]


# ---------------------------------------------------------------------------
# Core pathway functions (pure, testable)
# ---------------------------------------------------------------------------

def compute_biogas(
    mass_by_class: dict[str, float],
    config: BioScanConfig,
    mass_factor: float = 1.0,
    moisture_offset: float = 0.0,
    bmp_factor: float = 1.0,
) -> tuple[float, float, float]:
    """Compute biogas pathway: CH₄ (Nm³), thermal kWh, electric kWh.

    Args:
        mass_by_class: Mass (kg) per class.
        config: Pipeline config with waste_factors and efficiencies.
        mass_factor: Multiplier on mass for uncertainty (e.g. 0.75 for low).
        moisture_offset: Additive offset on moisture (e.g. +0.10 for low).
        bmp_factor: Multiplier on BMP for uncertainty.

    Returns:
        Tuple of (ch4_nm3, thermal_kwh, elec_kwh).
    """
    total_ch4 = 0.0
    for cls, mass_kg in mass_by_class.items():
        if cls not in config.waste_factors:
            continue
        f = config.waste_factors[cls]
        m = mass_kg * mass_factor

        moisture = min(f.moisture + moisture_offset, 0.99)  # cap at 0.99
        moisture = max(moisture, 0.0)

        dry_kg = m * (1.0 - moisture)
        vs_kg = dry_kg * f.vs_fraction
        ch4_c = vs_kg * f.bmp_nm3_ch4_per_kg_vs * bmp_factor

        total_ch4 += ch4_c

    thermal_kwh = total_ch4 * config.methane_lhv_kwh_per_nm3
    elec_kwh = thermal_kwh * config.chp_efficiency

    return total_ch4, thermal_kwh, elec_kwh


def compute_incineration(
    mass_by_class: dict[str, float],
    config: BioScanConfig,
    mass_factor: float = 1.0,
    lhv_factor: float = 1.0,
) -> tuple[float, float, float]:
    """Compute incineration pathway: heat MJ, thermal kWh, electric kWh.

    Args:
        mass_by_class: Mass (kg) per class.
        config: Pipeline config with waste_factors and efficiencies.
        mass_factor: Multiplier on mass for uncertainty.
        lhv_factor: Multiplier on LHV for uncertainty.

    Returns:
        Tuple of (heat_mj, thermal_kwh, elec_kwh).
    """
    total_mj = 0.0
    for cls, mass_kg in mass_by_class.items():
        if cls not in config.waste_factors:
            continue
        f = config.waste_factors[cls]
        m = mass_kg * mass_factor
        total_mj += m * f.lhv_mj_per_kg * lhv_factor

    thermal_kwh = total_mj / 3.6
    elec_kwh = thermal_kwh * config.wte_efficiency

    return total_mj, thermal_kwh, elec_kwh


# ---------------------------------------------------------------------------
# Recommendation logic (design.md §4.6)
# ---------------------------------------------------------------------------

def recommend(
    batch: Batch,
    elec_biogas_mid: float,
    elec_wte_mid: float,
    config: BioScanConfig,
) -> tuple[str, str]:
    """Determine the recommended pathway for a batch.

    Returns:
        (recommendation, reason) tuple.
        recommendation is one of: 'biogas', 'incineration', 'mixed', 'reject'.
    """
    group_fracs = batch.group_fractions(config.groups)
    comp = batch.composition_fractions()
    thr = config.thresholds

    inert_frac = group_fracs.get("inert", 0.0)
    organic_frac = group_fracs.get("organic", 0.0)
    plastic_frac = comp.get("plastic", 0.0)

    # Rule 1: Reject if mostly inert
    if inert_frac >= thr.reject_inert_fraction:
        return "reject", (
            f"Mostly non-combustible material ({inert_frac:.0%} inert). "
            f"Sort before energy recovery."
        )

    # Rule 2: Biogas if organic-rich, low plastic, and yield is competitive
    if (
        organic_frac >= thr.min_organic_fraction_biogas
        and plastic_frac <= thr.digester_max_plastic_fraction
        and elec_biogas_mid >= elec_wte_mid * 0.8
    ):
        return "biogas", (
            f"Organic-rich batch ({organic_frac:.0%} organic, "
            f"{plastic_frac:.0%} plastic). "
            f"Biogas yield {elec_biogas_mid:.1f} kWh vs. "
            f"incineration {elec_wte_mid:.1f} kWh."
        )

    # Rule 3: Incineration if WTE beats biogas
    if elec_wte_mid > elec_biogas_mid:
        return "incineration", (
            f"Higher energy via incineration ({elec_wte_mid:.1f} kWh) "
            f"than biogas ({elec_biogas_mid:.1f} kWh). "
            f"Combustible fraction: {group_fracs.get('combustible', 0.0):.0%}."
        )

    # Rule 4: Mixed
    return "mixed", (
        f"Split organics ({organic_frac:.0%}) to biogas and "
        f"combustibles ({group_fracs.get('combustible', 0.0):.0%}) to incineration."
    )


# ---------------------------------------------------------------------------
# Main evaluation: ties everything together with low/mid/high
# ---------------------------------------------------------------------------

class EnergyEngine:
    """Evaluate a batch through both energy pathways. Matches design.md §2."""

    def __init__(self, config: BioScanConfig) -> None:
        self._config = config

    def evaluate(self, batch: Batch) -> BatchEnergy:
        """Compute energy estimates with uncertainty for both pathways.

        Implements design.md §4.5 uncertainty bounding:
          low:  mass×(1-mass_rel), moisture+abs, BMP×(1-bmp_rel), LHV×(1-lhv_rel)
          mid:  nominal
          high: mass×(1+mass_rel), moisture-abs, BMP×(1+bmp_rel), LHV×(1+lhv_rel)
        """
        cfg = self._config
        unc = cfg.uncertainty
        m = batch.mass_by_class

        # --- Biogas pathway ---
        bg_low = compute_biogas(
            m, cfg,
            mass_factor=1.0 - unc.mass_rel,
            moisture_offset=+unc.moisture_abs,
            bmp_factor=1.0 - unc.bmp_rel,
        )
        bg_mid = compute_biogas(m, cfg)
        bg_high = compute_biogas(
            m, cfg,
            mass_factor=1.0 + unc.mass_rel,
            moisture_offset=-unc.moisture_abs,
            bmp_factor=1.0 + unc.bmp_rel,
        )

        ch4 = EnergyResult(bg_low[0], bg_mid[0], bg_high[0])
        th_bg = EnergyResult(bg_low[1], bg_mid[1], bg_high[1])
        el_bg = EnergyResult(bg_low[2], bg_mid[2], bg_high[2])

        # --- Incineration pathway ---
        wte_low = compute_incineration(
            m, cfg,
            mass_factor=1.0 - unc.mass_rel,
            lhv_factor=1.0 - unc.lhv_rel,
        )
        wte_mid = compute_incineration(m, cfg)
        wte_high = compute_incineration(
            m, cfg,
            mass_factor=1.0 + unc.mass_rel,
            lhv_factor=1.0 + unc.lhv_rel,
        )

        heat_mj = EnergyResult(wte_low[0], wte_mid[0], wte_high[0])
        th_wte = EnergyResult(wte_low[1], wte_mid[1], wte_high[1])
        el_wte = EnergyResult(wte_low[2], wte_mid[2], wte_high[2])

        # --- Recommendation ---
        rec, reason = recommend(batch, el_bg.mid, el_wte.mid, cfg)

        return BatchEnergy(
            ch4_nm3=ch4,
            thermal_biogas_kwh=th_bg,
            elec_biogas_kwh=el_bg,
            heat_mj=heat_mj,
            thermal_wte_kwh=th_wte,
            elec_wte_kwh=el_wte,
            recommendation=rec,
            reason=reason,
            hazard_flags=batch.hazard_flags,
        )

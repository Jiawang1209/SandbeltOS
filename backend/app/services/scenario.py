"""Afforestation scenario simulation.

Closed-form multi-year projection: given current FVC / soil moisture /
precipitation / wind, plus a planting plan (species, additional density,
years), iterate yearly to project FVC, SM, and desertification risk.

Risk math is delegated to `indicators.assess_risk` — single source of
truth. This module only models the *driver* dynamics (water balance and
its feedback on FVC) and lets `indicators` translate state into a risk
score.

## Calibration honesty

This is a regional-scale demo model. The water-balance coefficients are
hand-tuned so that:
  * drought-tolerant shrubs (caragana, seabuckthorn) remain stable
    around realistic three-north precipitation (≈250 mm/yr);
  * water-hungry trees (poplar, willow) at high density show clear
    decline ("small old tree" effect) under the same rainfall.

Coefficients are NOT calibrated against measured plot data. The model
is suitable for *qualitative* what-if exploration and decision support
visualisation, not for permitting decisions or quantitative yield
forecasts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from app.services.indicators import (
    RISK_LEVEL_LABELS,
    assess_risk,
    calculate_wind_erosion,
)

Species = Literal[
    "poplar", "willow", "pine", "elm", "seabuckthorn", "caragana"
]

# Annual ET demand (mm/yr) for a fully-stocked stand of this species in
# semi-arid sandy land. Sources: regional literature surveyed in
# ARCHITECTURE.md §8; uncertainty bound is roughly ±30% per row.
SPECIES_WATER_USE_MM: dict[Species, float] = {
    "poplar": 750,        # 杨树 — water-hungry, common but problematic
    "willow": 700,        # 柳树
    "pine": 450,          # 樟子松 — moderate
    "elm": 380,           # 榆树 — moderate, native
    "seabuckthorn": 300,  # 沙棘 — drought-tolerant shrub
    "caragana": 200,      # 柠条 — most drought-tolerant
}

SPECIES_LABELS_CN: dict[Species, str] = {
    "poplar": "杨树",
    "willow": "柳树",
    "pine": "樟子松",
    "elm": "榆树",
    "seabuckthorn": "沙棘",
    "caragana": "柠条",
}

# Per-tree water demand scale: water_use_per_tree = species_mm / 1000.
# Tuned against the calibration goals above (see module docstring).
_TREE_DEMAND_DIVISOR = 1000.0

# Fraction of annual precipitation actually plant-available (rest lost
# to runoff, deep drainage, and bare-soil evaporation). 30% is the
# canonical rule-of-thumb for semi-arid sandy soils.
EFFECTIVE_PRECIP_FRACTION = 0.30

# Sensitivity of root-zone SM to annual water deficit. Smaller = gentler
# year-over-year drift. 0.0002 keeps caragana stable and poplar stressed
# in the calibration scenarios; revisit when real soil-moisture data
# arrives.
SM_DEFICIT_COEF = 0.0002

# SM floor: physical residual under any conditions.
SM_FLOOR = 0.02

# SM stress threshold for FVC decay onset. Below this, plants struggle.
SM_STRESS_THRESHOLD = 0.04

# SM saturation reference — fully sufficient for plant growth.
SM_OPTIMUM = 0.15

# FVC dynamics
FVC_FLOOR = 0.02      # bare-ground asymptote under terminal stress
FVC_CEILING = 0.95    # maximum achievable cover
FVC_GROWTH_RATE = 0.02   # annual fractional gain in surplus years
FVC_STRESS_COEF = 0.05   # annual fractional decay scale at full stress

# Default wind speed used by the scenario when callers don't pass one.
# 4 m/s is the regional annual mean for Korqin / Hunshandake.
DEFAULT_WIND_SPEED_MS = 4.0

MAX_YEARS = 20
MIN_YEARS = 1


@dataclass(frozen=True)
class ScenarioInput:
    region_id: int
    current_fvc: float
    current_soil_moisture: float
    annual_precip_mm: float
    avg_wind_speed_ms: float
    species: Species
    additional_density_per_ha: int
    years: int


@dataclass(frozen=True)
class YearlyProjection:
    year: int
    fvc: float
    soil_moisture: float
    water_deficit_mm: float
    wind_erosion: float
    risk_level: int
    risk_label: str
    risk_score: float
    warning: str | None


@dataclass(frozen=True)
class ScenarioResult:
    region_id: int
    species: Species
    species_label: str
    additional_density_per_ha: int
    years: int
    yearly: list[YearlyProjection]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def annual_water_demand_mm(species: Species, density_per_ha: int) -> float:
    """Annual ET demand (mm/yr) from `density_per_ha` trees of `species`.

    Linear in density: each tree consumes `species_mm / _TREE_DEMAND_DIVISOR`
    mm/yr of stand-level water column. Returns 0 for zero density.
    """
    if density_per_ha < 0:
        raise ValueError("density must be non-negative")
    use_per_tree = SPECIES_WATER_USE_MM[species] / _TREE_DEMAND_DIVISOR
    return use_per_tree * density_per_ha


def simulate(scenario: ScenarioInput) -> ScenarioResult:
    """Project FVC / SM / risk over `scenario.years` under the planting plan.

    Each year, recompute water deficit, drift SM, update FVC via the
    stress-vs-surplus dynamics, then call `indicators.assess_risk` for
    the year-end risk level.
    """
    if not (MIN_YEARS <= scenario.years <= MAX_YEARS):
        raise ValueError(
            f"years must be in [{MIN_YEARS}, {MAX_YEARS}], got {scenario.years}"
        )

    demand_mm = annual_water_demand_mm(
        scenario.species, scenario.additional_density_per_ha
    )
    effective_precip = scenario.annual_precip_mm * EFFECTIVE_PRECIP_FRACTION

    sm = scenario.current_soil_moisture
    fvc = scenario.current_fvc
    yearly: list[YearlyProjection] = []

    for y in range(1, scenario.years + 1):
        deficit = max(0.0, demand_mm - effective_precip)

        if deficit > 0:
            sm = max(SM_FLOOR, sm - deficit * SM_DEFICIT_COEF)
            # Stress 0..1, where 1 = no stress (SM at optimum or above),
            # 0 = SM at or below SM_STRESS_THRESHOLD.
            stress_relief = max(
                0.0,
                min(1.0, (sm - SM_STRESS_THRESHOLD) / (SM_OPTIMUM - SM_STRESS_THRESHOLD)),
            )
            # When stress_relief = 1 → no FVC loss; when 0 → full FVC_STRESS_COEF loss.
            fvc = max(FVC_FLOOR, fvc * (1 - FVC_STRESS_COEF * (1 - stress_relief)))
        else:
            # Surplus year — slow FVC recovery toward ceiling.
            fvc = min(FVC_CEILING, fvc * (1 + FVC_GROWTH_RATE))

        wem = calculate_wind_erosion(scenario.avg_wind_speed_ms, fvc, sm)
        risk = assess_risk(fvc=fvc, wind_erosion=wem, soil_moisture=sm, lst_c=None)

        yearly.append(
            YearlyProjection(
                year=y,
                fvc=round(fvc, 4),
                soil_moisture=round(sm, 4),
                water_deficit_mm=round(deficit, 1),
                wind_erosion=round(wem, 1),
                risk_level=risk.risk_level,
                risk_label=RISK_LEVEL_LABELS[risk.risk_level],
                risk_score=risk.risk_score,
                warning=_year_warning(sm, fvc),
            )
        )

    return ScenarioResult(
        region_id=scenario.region_id,
        species=scenario.species,
        species_label=SPECIES_LABELS_CN[scenario.species],
        additional_density_per_ha=scenario.additional_density_per_ha,
        years=scenario.years,
        yearly=yearly,
        recommendation=_generate_recommendation(scenario, yearly),
    )


def _year_warning(sm: float, fvc: float) -> str | None:
    """Per-year warning text; None when conditions are acceptable."""
    if sm <= SM_STRESS_THRESHOLD:
        return "土壤水分接近极限阈值,植被可能进入持续衰退（'小老树'风险）"
    if fvc <= FVC_FLOOR * 2:
        return "植被覆盖度严重下降,建议调整造林密度或更换抗旱树种"
    return None


def _generate_recommendation(
    scenario: ScenarioInput, yearly: list[YearlyProjection]
) -> str:
    """Heuristic Chinese recommendation based on final-year and worst-year state."""
    final = yearly[-1]
    worst_sm = min(p.soil_moisture for p in yearly)
    species_cn = SPECIES_LABELS_CN[scenario.species]
    density = scenario.additional_density_per_ha
    precip = scenario.annual_precip_mm

    if final.risk_level >= 3:
        return (
            f"【高风险】在 {precip:.0f}mm/年 的降水条件下,以 {density} 株/公顷的密度"
            f"加种 {species_cn},{scenario.years} 年后达到「{final.risk_label}」。"
            "建议将密度降至 ≤ 300 株/公顷,或改用沙棘、柠条等抗旱树种。"
        )
    if final.risk_level == 2:
        return (
            f"【中等风险】{species_cn} {density} 株/公顷方案在 {scenario.years} 年后"
            f"风险等级为「{final.risk_label}」,土壤水分最低降至 {worst_sm:.3f} m³/m³。"
            "建议密切监测土壤水分,必要时阶段性疏伐降低密度。"
        )
    return (
        f"【低风险】{species_cn} {density} 株/公顷方案可行,{scenario.years} 年后"
        f"风险维持「{final.risk_label}」,土壤水分最低 {worst_sm:.3f} m³/m³。"
        "继续监测 NDVI 和土壤水分趋势即可。"
    )

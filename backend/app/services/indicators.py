"""
Ecological indicator calculations for SandbeltOS.

Pure functions, no I/O. Formulas are regional-scale proxies calibrated for
semi-arid sandy land (Korqin / Hunshandake). Each function takes scalar inputs
and returns a scalar output so they can be called from tests, batch jobs, or
on-demand APIs.

References:
    FVC — Carlson & Ripley (1997), dimidiate pixel model.
    Wind Erosion — Fryrear et al. (2000), RWEQ simplified to regional proxy.
    Carbon Density — linear NDVI proxy for arid grassland/shrubland biomass.
"""

from __future__ import annotations

from dataclasses import dataclass

# NDVI-to-FVC reference endpoints (bare soil / fully vegetated)
NDVI_SOIL = 0.05
NDVI_VEG = 0.75

# Wind erosion proxy — scales output to t/(km²·month) order of magnitude
WIND_EROSION_K = 50.0
WIND_EROSION_SM_DECAY = 5.0  # exp decay coefficient for soil moisture

# Carbon density proxy — NDVI → gC/m² for semi-arid vegetation
CARBON_NDVI_OFFSET = 0.05
CARBON_NDVI_COEF = 1500.0

# Risk weights (must sum to 1)
RISK_WEIGHTS = {
    "fvc": 0.35,
    "wind_erosion": 0.30,
    "soil_moisture": 0.20,
    "thermal": 0.15,
}

# Wind erosion threshold for risk normalization (t/km²·month)
WEM_RISK_THRESHOLD = 200.0

# Thermal anomaly reference (°C) — deviation from regional optimum
LST_OPTIMUM_C = 15.0
LST_ANOMALY_SCALE = 30.0


def calculate_fvc(
    ndvi: float,
    ndvi_soil: float = NDVI_SOIL,
    ndvi_veg: float = NDVI_VEG,
) -> float:
    """Fractional Vegetation Cover from NDVI (dimidiate pixel model)."""
    if ndvi_veg <= ndvi_soil:
        raise ValueError("ndvi_veg must exceed ndvi_soil")
    fvc = (ndvi - ndvi_soil) / (ndvi_veg - ndvi_soil)
    return max(0.0, min(1.0, fvc))


def calculate_wind_erosion(
    wind_speed_ms: float,
    fvc: float,
    soil_moisture: float | None = None,
) -> float:
    """Wind erosion modulus proxy in t/(km²·month).

    WEM = k * U^3 * (1 - FVC) * exp(-SM * decay)

    Scales with cube of wind speed, inversely with vegetation cover, and
    damped by surface soil moisture. Returns 0 when wind speed <= 0.
    """
    if wind_speed_ms <= 0:
        return 0.0
    veg_factor = max(0.0, 1.0 - fvc)
    sm = soil_moisture if soil_moisture is not None else 0.0
    import math
    moisture_factor = math.exp(-max(0.0, sm) * WIND_EROSION_SM_DECAY)
    return WIND_EROSION_K * (wind_speed_ms ** 3) * veg_factor * moisture_factor


def calculate_sand_fixation(
    wind_speed_ms: float,
    fvc: float,
    soil_moisture: float | None = None,
) -> float:
    """Sand fixation service amount: potential minus actual erosion.

    Difference between erosion if the land were bare (FVC=0) and current
    vegetation-damped erosion. Always non-negative. Unit: t/(km²·month).
    """
    potential = calculate_wind_erosion(wind_speed_ms, 0.0, soil_moisture)
    actual = calculate_wind_erosion(wind_speed_ms, fvc, soil_moisture)
    return max(0.0, potential - actual)


def calculate_carbon_density(ndvi: float) -> float:
    """Above-ground carbon density proxy in gC/m² (semi-arid vegetation)."""
    return CARBON_NDVI_COEF * max(0.0, ndvi - CARBON_NDVI_OFFSET)


@dataclass(frozen=True)
class RiskAssessment:
    risk_score: float  # 0..1
    risk_level: int  # 1 低, 2 中, 3 高, 4 极高
    factors: dict[str, float]


def assess_risk(
    fvc: float,
    wind_erosion: float,
    soil_moisture: float | None,
    lst_c: float | None,
) -> RiskAssessment:
    """Composite desertification risk assessment.

    Each factor is normalized to [0,1] risk contribution, then weighted-summed.
    Missing factors (None) are dropped and remaining weights re-normalized.
    """
    contributions: dict[str, float] = {}

    # Vegetation cover — lower → higher risk
    contributions["fvc"] = max(0.0, min(1.0, 1.0 - fvc))

    # Wind erosion — scaled by threshold
    contributions["wind_erosion"] = min(1.0, wind_erosion / WEM_RISK_THRESHOLD)

    if soil_moisture is not None:
        # Lower moisture → higher risk (SM is typically 0..0.5 m³/m³)
        contributions["soil_moisture"] = max(0.0, 1.0 - soil_moisture * 4.0)

    if lst_c is not None:
        # Deviation from optimum — hot or cold extremes both raise risk
        contributions["thermal"] = min(
            1.0, abs(lst_c - LST_OPTIMUM_C) / LST_ANOMALY_SCALE
        )

    active_weights = {k: RISK_WEIGHTS[k] for k in contributions}
    weight_sum = sum(active_weights.values())
    if weight_sum == 0:
        raise ValueError("no active risk factors")

    score = sum(
        contributions[k] * (active_weights[k] / weight_sum)
        for k in contributions
    )
    level = _score_to_level(score)

    return RiskAssessment(
        risk_score=round(score, 4),
        risk_level=level,
        factors={k: round(v, 4) for k, v in contributions.items()},
    )


def _score_to_level(score: float) -> int:
    if score < 0.25:
        return 1
    if score < 0.5:
        return 2
    if score < 0.75:
        return 3
    return 4


RISK_LEVEL_LABELS: dict[int, str] = {
    1: "低风险",
    2: "中等风险",
    3: "高风险",
    4: "极高风险",
}

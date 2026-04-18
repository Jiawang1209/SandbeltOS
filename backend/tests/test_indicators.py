"""Unit tests for ecological indicator formulas."""

import math

import pytest

from app.services.indicators import (
    assess_risk,
    calculate_carbon_density,
    calculate_fvc,
    calculate_sand_fixation,
    calculate_wind_erosion,
)


# ---------- FVC ----------

@pytest.mark.unit
class TestFvc:
    def test_bare_soil_is_zero(self) -> None:
        assert calculate_fvc(0.05) == 0.0

    def test_fully_vegetated_is_one(self) -> None:
        assert calculate_fvc(0.75) == 1.0

    def test_mid_range_is_bounded(self) -> None:
        v = calculate_fvc(0.4)
        assert 0 < v < 1

    def test_below_soil_clips_to_zero(self) -> None:
        assert calculate_fvc(-0.2) == 0.0

    def test_above_veg_clips_to_one(self) -> None:
        assert calculate_fvc(0.95) == 1.0

    def test_invalid_endpoints_raise(self) -> None:
        with pytest.raises(ValueError):
            calculate_fvc(0.3, ndvi_soil=0.8, ndvi_veg=0.5)


# ---------- Wind erosion ----------

@pytest.mark.unit
class TestWindErosion:
    def test_zero_wind_is_zero(self) -> None:
        assert calculate_wind_erosion(0, fvc=0.1) == 0.0

    def test_full_cover_is_zero(self) -> None:
        assert calculate_wind_erosion(10, fvc=1.0) == 0.0

    def test_cubed_scaling_with_wind(self) -> None:
        low = calculate_wind_erosion(2, fvc=0.2)
        high = calculate_wind_erosion(4, fvc=0.2)
        assert high == pytest.approx(low * 8, rel=1e-6)

    def test_moisture_reduces_erosion(self) -> None:
        dry = calculate_wind_erosion(5, fvc=0.3, soil_moisture=0.05)
        wet = calculate_wind_erosion(5, fvc=0.3, soil_moisture=0.4)
        assert dry > wet > 0

    def test_reasonable_magnitude(self) -> None:
        # 5 m/s wind, FVC 0.3, no moisture → order of thousands t/km²·month
        wem = calculate_wind_erosion(5, fvc=0.3, soil_moisture=0.0)
        assert 1000 < wem < 10000


# ---------- Sand fixation ----------

@pytest.mark.unit
class TestSandFixation:
    def test_non_negative(self) -> None:
        sf = calculate_sand_fixation(7, fvc=0.4, soil_moisture=0.1)
        assert sf >= 0

    def test_bare_land_no_service(self) -> None:
        assert calculate_sand_fixation(5, fvc=0.0) == 0.0

    def test_full_cover_full_service(self) -> None:
        sf = calculate_sand_fixation(6, fvc=1.0)
        potential = calculate_wind_erosion(6, fvc=0.0)
        assert sf == pytest.approx(potential)


# ---------- Carbon density ----------

@pytest.mark.unit
class TestCarbonDensity:
    def test_below_offset_is_zero(self) -> None:
        assert calculate_carbon_density(0.02) == 0.0

    def test_monotonic(self) -> None:
        assert calculate_carbon_density(0.3) < calculate_carbon_density(0.5)

    def test_reasonable_range(self) -> None:
        # NDVI 0.4 (moderate veg) → ~500 gC/m²
        c = calculate_carbon_density(0.4)
        assert 300 < c < 800


# ---------- Composite risk ----------

@pytest.mark.unit
class TestRiskAssessment:
    def test_healthy_land_is_low_risk(self) -> None:
        r = assess_risk(fvc=0.8, wind_erosion=10, soil_moisture=0.3, lst_c=16)
        assert r.risk_level == 1
        assert 0 <= r.risk_score < 0.25

    def test_bare_windy_land_is_extreme(self) -> None:
        r = assess_risk(fvc=0.05, wind_erosion=500, soil_moisture=0.02, lst_c=40)
        assert r.risk_level == 4
        assert r.risk_score >= 0.75

    def test_score_bounds(self) -> None:
        r = assess_risk(fvc=0.4, wind_erosion=100, soil_moisture=0.15, lst_c=20)
        assert 0 <= r.risk_score <= 1
        assert 1 <= r.risk_level <= 4

    def test_missing_factors_are_excluded(self) -> None:
        r = assess_risk(fvc=0.3, wind_erosion=80, soil_moisture=None, lst_c=None)
        assert "soil_moisture" not in r.factors
        assert "thermal" not in r.factors
        assert "fvc" in r.factors and "wind_erosion" in r.factors

    def test_level_boundary_at_0_5(self) -> None:
        # A manufactured score close to 0.5
        r = assess_risk(fvc=0.3, wind_erosion=100, soil_moisture=0.1, lst_c=22)
        # Should fall in level 2 or 3 based on score
        assert r.risk_level in (2, 3)
        assert math.isclose(
            r.risk_score,
            sum(r.factors[k] * w for k, w in _active_weights(r.factors).items()),
            rel_tol=1e-3,
        )


def _active_weights(factors: dict[str, float]) -> dict[str, float]:
    from app.services.indicators import RISK_WEIGHTS
    active = {k: RISK_WEIGHTS[k] for k in factors}
    total = sum(active.values())
    return {k: v / total for k, v in active.items()}

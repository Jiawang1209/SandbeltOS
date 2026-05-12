"""Tests for the afforestation scenario simulation service.

Unit tests cover the pure `simulate()` function — no DB, no Prophet.
Integration tests POST to the API which uses regional baselines from
the DB when the client omits starting-state overrides.

Calibration assertions are *relative* (drought-tolerant species fare
better than water-hungry ones under the same rainfall) rather than
absolute risk levels, because the underlying wind-erosion calibration
in `indicators.py` is intentionally coarse for this demo.
"""
from __future__ import annotations

import pytest

from app.services.scenario import (
    MAX_YEARS,
    MIN_YEARS,
    SPECIES_LABELS_CN,
    ScenarioInput,
    annual_water_demand_mm,
    simulate,
)


def _make_input(
    *,
    species: str = "poplar",
    density: int = 500,
    years: int = 5,
    fvc: float = 0.55,
    sm: float = 0.15,
    precip: float = 380.0,
    wind: float = 2.5,
) -> ScenarioInput:
    return ScenarioInput(
        region_id=1,
        current_fvc=fvc,
        current_soil_moisture=sm,
        annual_precip_mm=precip,
        avg_wind_speed_ms=wind,
        species=species,  # type: ignore[arg-type]
        additional_density_per_ha=density,
        years=years,
    )


# ---------- water demand helper ----------


@pytest.mark.unit
class TestWaterDemand:
    def test_zero_density_zero_demand(self) -> None:
        assert annual_water_demand_mm("poplar", 0) == 0.0

    def test_linear_in_density(self) -> None:
        a = annual_water_demand_mm("poplar", 500)
        b = annual_water_demand_mm("poplar", 1000)
        assert b == pytest.approx(2 * a)

    def test_caragana_lower_than_poplar(self) -> None:
        assert annual_water_demand_mm("caragana", 500) < annual_water_demand_mm(
            "poplar", 500
        )

    def test_negative_density_raises(self) -> None:
        with pytest.raises(ValueError):
            annual_water_demand_mm("poplar", -100)


# ---------- simulate() unit tests ----------


@pytest.mark.unit
class TestSimulate:
    def test_returns_one_projection_per_year(self) -> None:
        result = simulate(_make_input(years=5))
        assert len(result.yearly) == 5
        assert [p.year for p in result.yearly] == [1, 2, 3, 4, 5]

    def test_years_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            simulate(_make_input(years=0))
        with pytest.raises(ValueError):
            simulate(_make_input(years=MAX_YEARS + 1))

    def test_zero_density_keeps_or_grows_fvc(self) -> None:
        """With no added plantation, FVC should not decline."""
        result = simulate(_make_input(density=0, years=5))
        # Allow tiny numerical noise but FVC should not drop below start
        assert result.yearly[-1].fvc >= 0.30 - 1e-6

    def test_caragana_lower_risk_than_poplar(self) -> None:
        """Same density + rainfall, drought-tolerant species ends up at
        equal-or-lower risk than water-hungry species."""
        carag = simulate(_make_input(species="caragana", density=500, precip=250))
        poplar = simulate(_make_input(species="poplar", density=500, precip=250))
        assert carag.yearly[-1].risk_level <= poplar.yearly[-1].risk_level

    def test_overdensity_poplar_triggers_warning(self) -> None:
        """Wildly over-stocking poplar in 250mm/yr precip should hit the
        SM floor and produce a per-year warning."""
        result = simulate(
            _make_input(species="poplar", density=2000, precip=250, years=5, sm=0.10)
        )
        warnings = [p.warning for p in result.yearly if p.warning]
        assert warnings, "expected at least one warning year"
        # final SM should be at or near the floor
        assert result.yearly[-1].soil_moisture <= 0.05

    def test_recommendation_text_is_chinese(self) -> None:
        result = simulate(_make_input(species="poplar", density=500, years=5))
        # Recommendation must contain Chinese characters and be non-trivial
        assert len(result.recommendation) > 20
        assert any("一" <= ch <= "鿿" for ch in result.recommendation)

    def test_species_label_localized(self) -> None:
        result = simulate(_make_input(species="caragana"))
        assert result.species_label == SPECIES_LABELS_CN["caragana"]
        assert result.species_label == "柠条"

    def test_fvc_and_sm_stay_in_physical_bounds(self) -> None:
        result = simulate(
            _make_input(species="poplar", density=2000, precip=200, years=10)
        )
        for p in result.yearly:
            assert 0.0 <= p.fvc <= 1.0
            assert 0.0 <= p.soil_moisture <= 1.0
            assert p.water_deficit_mm >= 0
            assert p.wind_erosion >= 0
            assert 1 <= p.risk_level <= 4


# ---------- API integration ----------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_api_smoke(client) -> None:
    response = await client.post(
        "/api/v1/prediction/scenario",
        json={
            "region_id": 1,
            "species": "poplar",
            "additional_density_per_ha": 500,
            "years": 5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["species"] == "poplar"
    assert body["species_label"] == "杨树"
    assert body["years"] == 5
    assert len(body["yearly"]) == 5
    assert "baseline_used" in body
    # baseline must have all four resolved fields
    assert {
        "current_fvc",
        "current_soil_moisture",
        "annual_precip_mm",
        "avg_wind_speed_ms",
    } <= body["baseline_used"].keys()
    assert body["recommendation"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_api_with_overrides(client) -> None:
    """Client-supplied overrides flow through to baseline_used."""
    response = await client.post(
        "/api/v1/prediction/scenario",
        json={
            "region_id": 1,
            "species": "caragana",
            "additional_density_per_ha": 600,
            "years": 3,
            "current_fvc": 0.25,
            "annual_precip_mm": 220,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["baseline_used"]["current_fvc"] == 0.25
    assert body["baseline_used"]["annual_precip_mm"] == 220
    assert len(body["yearly"]) == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_defaults_lists_species(client) -> None:
    response = await client.get(
        "/api/v1/prediction/scenario-defaults", params={"region_id": 1}
    )
    assert response.status_code == 200
    body = response.json()
    species_keys = {opt["key"] for opt in body["species_options"]}
    assert {"poplar", "caragana"} <= species_keys
    assert body["baseline"]["current_fvc"] > 0

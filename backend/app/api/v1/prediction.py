"""Phase 5 prediction & scenario routes.

Two endpoints:

* `GET  /api/v1/prediction/ndvi-forecast` — Prophet NDVI forecast over
  `horizon` × 16-day steps. Cached for 30 min keyed on (region, horizon,
  today).
* `POST /api/v1/prediction/scenario` — afforestation what-if. Client
  picks species / density / years; server fills regional baselines for
  the optional starting-state knobs and returns a multi-year projection.

Implementation invariants:
* Routers stay thin — orchestration lives in the service modules.
* Invalid input → 400 with an explanatory `detail`; missing region or
  insufficient history → 404 / 422 respectively.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.limiter import limiter
from app.services import ecological as eco_svc
from app.services import prediction as pred_svc
from app.services import scenario as scenario_svc
from app.services.scenario import (
    SPECIES_LABELS_CN,
    SPECIES_WATER_USE_MM,
    ScenarioInput,
    Species,
)

router = APIRouter()
_settings = get_settings()


# ---------- regional baselines (used when client omits scenario knobs) ----------

# Sensible defaults for the two seeded regions. Calibration note:
# the wind speed here is the *annual mean useful* value (~2.5 m/s),
# not peak gusts — indicators.calculate_wind_erosion is a cube-law
# proxy so even modest wind values dominate risk if we use peak winds.
# Starting FVC reflects "moderately managed sandy land" (the regions
# we're currently afforesting), not "bare dune". When real GEE data
# lands, swap these for the latest-year regional mean.
REGIONAL_BASELINES: dict[int, dict[str, float]] = {
    1: {  # Horqin 科尔沁
        "current_fvc": 0.55,
        "current_soil_moisture": 0.15,
        "annual_precip_mm": 380.0,
        "avg_wind_speed_ms": 2.5,
    },
    2: {  # Hunshandake 浑善达克
        "current_fvc": 0.50,
        "current_soil_moisture": 0.13,
        "annual_precip_mm": 340.0,
        "avg_wind_speed_ms": 2.7,
    },
}

_FALLBACK_BASELINE = {
    "current_fvc": 0.55,
    "current_soil_moisture": 0.15,
    "annual_precip_mm": 380.0,
    "avg_wind_speed_ms": 2.5,
}


async def _resolve_baseline(region_id: int, db: AsyncSession) -> dict[str, float]:
    """Best-effort starting state. Prefers fresh DB readings, falls back
    to hardcoded regional defaults, then to a global fallback.

    Annual precip currently comes from the regional baseline only —
    weather_latest gives the single latest day, not an annual sum. When
    real ERA5 ingestion ships we should swap to a 12-month rolling sum.
    """
    base = dict(REGIONAL_BASELINES.get(region_id, _FALLBACK_BASELINE))

    # Soil moisture: prefer freshly measured value if available.
    latest = await eco_svc.get_weather_latest(region_id, db)
    if latest is not None:
        if latest.get("soil_moisture") is not None:
            base["current_soil_moisture"] = float(latest["soil_moisture"])
        if latest.get("wind_speed") is not None:
            base["avg_wind_speed_ms"] = float(latest["wind_speed"])

    # FVC: from latest NDVI/FVC row if present.
    fvc = await eco_svc.get_ndvi_fvc_latest(region_id, db)
    if fvc is not None and fvc.get("fvc") is not None:
        base["current_fvc"] = float(fvc["fvc"])

    return base


# ---------- request / response models ----------


class ForecastPointModel(BaseModel):
    date: str
    yhat: float
    yhat_lower: float
    yhat_upper: float


class ForecastResponse(BaseModel):
    region_id: int
    indicator: str
    model: Literal["prophet"]
    fitted_on_n_points: int
    history_end: str
    horizon_steps: int
    freq: str
    points: list[ForecastPointModel]


class ScenarioRequest(BaseModel):
    region_id: int = 1
    species: Species
    additional_density_per_ha: int = Field(..., ge=0, le=5000)
    years: int = Field(5, ge=scenario_svc.MIN_YEARS, le=scenario_svc.MAX_YEARS)
    # Optional starting-state overrides. When omitted, the server fills
    # them in via _resolve_baseline.
    current_fvc: float | None = Field(default=None, ge=0.0, le=1.0)
    current_soil_moisture: float | None = Field(default=None, ge=0.0, le=1.0)
    annual_precip_mm: float | None = Field(default=None, ge=0.0, le=2000.0)
    avg_wind_speed_ms: float | None = Field(default=None, ge=0.0, le=30.0)


class YearlyProjectionModel(BaseModel):
    year: int
    fvc: float
    soil_moisture: float
    water_deficit_mm: float
    wind_erosion: float
    risk_level: int
    risk_label: str
    risk_score: float
    warning: str | None


class ScenarioResponse(BaseModel):
    region_id: int
    species: str
    species_label: str
    additional_density_per_ha: int
    years: int
    baseline_used: dict[str, float]
    yearly: list[YearlyProjectionModel]
    recommendation: str


class SpeciesOption(BaseModel):
    key: str
    label_cn: str
    water_use_mm: float


class ScenarioDefaultsResponse(BaseModel):
    region_id: int
    baseline: dict[str, float]
    species_options: list[SpeciesOption]


# ---------- routes ----------


@router.get("/ndvi-forecast", response_model=ForecastResponse)
async def get_ndvi_forecast(
    region_id: int = Query(1, description="Region ID"),
    horizon: int = Query(
        12, ge=1, le=24, description="Forecast steps ahead (each 16 days)"
    ),
    db: AsyncSession = Depends(get_db),
) -> ForecastResponse:
    """NDVI 未来 N 期(每期 16 天)Prophet 预测。默认 12 期 ≈ 半年。"""
    try:
        result = await pred_svc.forecast_indicator(
            region_id=region_id,
            indicator="ndvi",
            horizon_steps=horizon,
            db=db,
        )
    except ValueError as exc:
        # insufficient history → 422 Unprocessable Entity (data-shape problem)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ForecastResponse(
        region_id=result.region_id,
        indicator=result.indicator,
        model=result.model,
        fitted_on_n_points=result.fitted_on_n_points,
        history_end=result.history_end,
        horizon_steps=result.horizon_steps,
        freq=result.freq,
        points=[ForecastPointModel(**p.__dict__) for p in result.points],
    )


@router.get("/scenario-defaults", response_model=ScenarioDefaultsResponse)
async def get_scenario_defaults(
    region_id: int = Query(1, description="Region ID"),
    db: AsyncSession = Depends(get_db),
) -> ScenarioDefaultsResponse:
    """Return the regional baseline + species catalog the UI uses to
    pre-fill the scenario form."""
    baseline = await _resolve_baseline(region_id, db)
    options = [
        SpeciesOption(
            key=key,
            label_cn=SPECIES_LABELS_CN[key],
            water_use_mm=SPECIES_WATER_USE_MM[key],
        )
        for key in SPECIES_WATER_USE_MM
    ]
    return ScenarioDefaultsResponse(
        region_id=region_id,
        baseline=baseline,
        species_options=options,
    )


@router.post("/scenario", response_model=ScenarioResponse)
@limiter.limit(_settings.scenario_rate_limit or _settings.api_rate_limit)
async def post_scenario(
    request: Request,  # noqa: ARG001 — required by slowapi key_func
    req: ScenarioRequest,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    """造林情景分析:树种 × 密度 × 年限 → 多年生态指标演化。

    Client may omit any of the four starting-state fields
    (current_fvc, current_soil_moisture, annual_precip_mm,
    avg_wind_speed_ms); the server fills them from regional defaults
    and returns the resolved values under `baseline_used` so the UI
    can show them next to the chart.
    """
    baseline = await _resolve_baseline(req.region_id, db)
    resolved: dict[str, float] = {
        "current_fvc": req.current_fvc if req.current_fvc is not None else baseline["current_fvc"],
        "current_soil_moisture": (
            req.current_soil_moisture
            if req.current_soil_moisture is not None
            else baseline["current_soil_moisture"]
        ),
        "annual_precip_mm": (
            req.annual_precip_mm
            if req.annual_precip_mm is not None
            else baseline["annual_precip_mm"]
        ),
        "avg_wind_speed_ms": (
            req.avg_wind_speed_ms
            if req.avg_wind_speed_ms is not None
            else baseline["avg_wind_speed_ms"]
        ),
    }

    scenario_input = ScenarioInput(
        region_id=req.region_id,
        current_fvc=resolved["current_fvc"],
        current_soil_moisture=resolved["current_soil_moisture"],
        annual_precip_mm=resolved["annual_precip_mm"],
        avg_wind_speed_ms=resolved["avg_wind_speed_ms"],
        species=req.species,
        additional_density_per_ha=req.additional_density_per_ha,
        years=req.years,
    )

    try:
        result = scenario_svc.simulate(scenario_input)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ScenarioResponse(
        region_id=result.region_id,
        species=result.species,
        species_label=result.species_label,
        additional_density_per_ha=result.additional_density_per_ha,
        years=result.years,
        baseline_used=resolved,
        yearly=[YearlyProjectionModel(**p.__dict__) for p in result.yearly],
        recommendation=result.recommendation,
    )

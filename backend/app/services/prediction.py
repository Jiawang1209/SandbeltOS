"""NDVI forecasting service.

Fits Prophet on `eco_indicators` history for one (region, indicator)
and returns horizon×freq future points (default 12 × 16D ≈ half a year).

Design notes:
* The pure compute step `forecast_series` takes a (ds, y) DataFrame and
  is independently testable — Prophet fit on 50 synthetic rows runs in
  well under a second.
* `forecast_indicator` is the async orchestrator that reads history via
  the ecological service, calls `forecast_series`, and optionally
  memoizes the result for the day in Redis.
* NDVI / FVC are physically bounded to [0,1]; Prophet does not know
  this, so all yhat/lower/upper values are clamped after prediction.
* `seasonality_mode='multiplicative'` is correct for vegetation indices
  whose annual swing scales with mean cover. Yearly seasonality only —
  16-day MODIS composites cannot resolve sub-monthly cycles.

Warning to future readers: when real GEE data lands, retune
`changepoint_prior_scale`. The current 0.05 is fine for the
mildly-trending synthetic series but may underfit real changepoints
after wildfire or large afforestation events.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import cache
from app.services import ecological as eco_svc

logger = logging.getLogger(__name__)

MIN_HISTORY_POINTS = 24
NDVI_CLAMP = (0.0, 1.0)
CACHE_TTL_SECONDS = 1800  # 30 min — see PLAN §1 D3
DEFAULT_FREQ = "16D"


@dataclass(frozen=True)
class ForecastPoint:
    date: str  # ISO YYYY-MM-DD
    yhat: float
    yhat_lower: float
    yhat_upper: float


@dataclass(frozen=True)
class ForecastResult:
    region_id: int
    indicator: str
    model: Literal["prophet"]
    fitted_on_n_points: int
    history_end: str  # ISO date of last observation
    horizon_steps: int
    freq: str
    points: list[ForecastPoint]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # points are already plain dicts after asdict
        return d


def forecast_series(
    history: pd.DataFrame,
    horizon_steps: int,
    freq: str = DEFAULT_FREQ,
    clamp: tuple[float, float] | None = NDVI_CLAMP,
) -> list[ForecastPoint]:
    """Fit Prophet on (ds, y) history and return `horizon_steps` forecasts.

    Raises ValueError when history has fewer than `MIN_HISTORY_POINTS`
    rows — Prophet's yearly seasonality fit becomes unreliable below
    that threshold.

    `clamp` is applied to yhat / yhat_lower / yhat_upper; pass None to
    disable (e.g. for indicators not bounded to [0,1]).
    """
    if not {"ds", "y"}.issubset(history.columns):
        raise ValueError("history must have columns ds, y")
    if len(history) < MIN_HISTORY_POINTS:
        raise ValueError(
            f"need >= {MIN_HISTORY_POINTS} history points to fit "
            f"yearly seasonality (got {len(history)})"
        )

    # Import here so test collection (and the rest of the API) doesn't
    # pay Prophet's ~1s import cost when this code path is unused.
    from prophet import Prophet

    # Silence Prophet/cmdstanpy noise — INFO logs every fit otherwise.
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
    logging.getLogger("prophet").setLevel(logging.WARNING)

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode="multiplicative",
        changepoint_prior_scale=0.05,
    )
    model.fit(history)

    future = model.make_future_dataframe(periods=horizon_steps, freq=freq)
    forecast = model.predict(future).tail(horizon_steps)

    lo, hi = clamp if clamp else (float("-inf"), float("inf"))
    points: list[ForecastPoint] = []
    for _, row in forecast.iterrows():
        points.append(
            ForecastPoint(
                date=row["ds"].strftime("%Y-%m-%d"),
                yhat=float(min(hi, max(lo, row["yhat"]))),
                yhat_lower=float(min(hi, max(lo, row["yhat_lower"]))),
                yhat_upper=float(min(hi, max(lo, row["yhat_upper"]))),
            )
        )
    return points


def _cache_key(region_id: int, indicator: str, horizon: int, day: date) -> str:
    return f"forecast:{region_id}:{indicator}:{horizon}:{day.isoformat()}"


async def forecast_indicator(
    region_id: int,
    indicator: str,
    horizon_steps: int,
    db: AsyncSession,
    freq: str = DEFAULT_FREQ,
    use_cache: bool = True,
) -> ForecastResult:
    """Forecast `indicator` for `region_id` `horizon_steps` ahead.

    Reads the full available history via the ecological service
    (start_date hardcoded far enough back to cover seeded data).
    """
    cache_key = _cache_key(region_id, indicator, horizon_steps, date.today())
    if use_cache:
        cached = await cache.get_json(cache_key)
        if cached is not None:
            logger.info("forecast cache hit for %s", cache_key)
            return _result_from_dict(cached)

    ts = await eco_svc.get_timeseries(
        region_id, indicator, "2000-01-01", "2099-12-31", db
    )
    if "error" in ts:
        raise ValueError(ts["error"])

    rows = ts.get("data", [])
    if len(rows) < MIN_HISTORY_POINTS:
        raise ValueError(
            f"region {region_id} has only {len(rows)} {indicator} points "
            f"(need >= {MIN_HISTORY_POINTS})"
        )

    df = pd.DataFrame(
        [{"ds": pd.to_datetime(r["time"]), "y": r["value"]} for r in rows]
    )

    points = forecast_series(df, horizon_steps, freq=freq)
    result = ForecastResult(
        region_id=region_id,
        indicator=indicator,
        model="prophet",
        fitted_on_n_points=len(df),
        history_end=df["ds"].iloc[-1].strftime("%Y-%m-%d"),
        horizon_steps=horizon_steps,
        freq=freq,
        points=points,
    )

    if use_cache:
        await cache.set_json(cache_key, result.to_dict(), ttl_seconds=CACHE_TTL_SECONDS)

    return result


def _result_from_dict(d: dict[str, Any]) -> ForecastResult:
    return ForecastResult(
        region_id=d["region_id"],
        indicator=d["indicator"],
        model=d["model"],
        fitted_on_n_points=d["fitted_on_n_points"],
        history_end=d["history_end"],
        horizon_steps=d["horizon_steps"],
        freq=d["freq"],
        points=[ForecastPoint(**p) for p in d["points"]],
    )

"""Tests for the Prophet NDVI forecasting service.

Unit tests cover the pure compute step `forecast_series` with synthetic
series (no DB, but does require Prophet installed). Integration tests
hit the API endpoint and therefore require a seeded DB on the default
DATABASE_URL.

`@pytest.mark.slow` is reserved for tests that would download a model
or pull large data; Prophet fits on a small series in under a second,
so these are NOT marked slow even though they exercise Prophet.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.services.prediction import (
    MIN_HISTORY_POINTS,
    ForecastPoint,
    forecast_series,
)


def _synthetic_ndvi_series(n_points: int, start: str = "2020-01-01") -> pd.DataFrame:
    """Generate a synthetic NDVI series with annual sinusoidal seasonality
    + mild upward trend. Used by unit tests that need >= MIN_HISTORY_POINTS
    rows but want deterministic behavior.
    """
    base_date = datetime.fromisoformat(start)
    rows = []
    for i in range(n_points):
        ds = base_date + timedelta(days=16 * i)
        # day-of-year seasonal swing 0.15 amplitude around 0.35 mean
        doy = ds.timetuple().tm_yday
        seasonal = 0.15 * np.sin(2 * np.pi * doy / 365.0)
        trend = 0.002 * i  # very mild upward trend
        y = 0.35 + seasonal + trend
        rows.append({"ds": ds, "y": y})
    return pd.DataFrame(rows)


# ---------- forecast_series unit tests ----------


@pytest.mark.unit
class TestForecastSeries:
    def test_returns_horizon_points(self) -> None:
        history = _synthetic_ndvi_series(60)
        points = forecast_series(history, horizon_steps=6, freq="16D")
        assert len(points) == 6
        assert all(isinstance(p, ForecastPoint) for p in points)

    def test_clamps_to_ndvi_bounds(self) -> None:
        """Even on a wild trend, yhat/lower/upper stay in [0,1]."""
        # Use a steeply rising series that Prophet would otherwise
        # extrapolate above 1
        history = _synthetic_ndvi_series(60)
        history["y"] = history["y"] + np.linspace(0, 0.6, len(history))
        points = forecast_series(history, horizon_steps=12, freq="16D")
        for p in points:
            assert 0.0 <= p.yhat <= 1.0
            assert 0.0 <= p.yhat_lower <= 1.0
            assert 0.0 <= p.yhat_upper <= 1.0
            # bounds ordered correctly
            assert p.yhat_lower <= p.yhat_upper

    def test_insufficient_history_raises(self) -> None:
        history = _synthetic_ndvi_series(MIN_HISTORY_POINTS - 1)
        with pytest.raises(ValueError, match="history points"):
            forecast_series(history, horizon_steps=6)

    def test_missing_columns_raises(self) -> None:
        bad = pd.DataFrame({"date": [1, 2, 3], "ndvi": [0.1, 0.2, 0.3]})
        with pytest.raises(ValueError, match="columns ds, y"):
            forecast_series(bad, horizon_steps=6)

    def test_dates_are_iso_strings(self) -> None:
        history = _synthetic_ndvi_series(50)
        points = forecast_series(history, horizon_steps=4, freq="16D")
        for p in points:
            # ISO YYYY-MM-DD
            datetime.fromisoformat(p.date)


# ---------- API integration ----------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forecast_api_smoke(client) -> None:
    """Hits the API against the seeded DB (region 1 has Phase-1 NDVI data)."""
    response = await client.get(
        "/api/v1/prediction/ndvi-forecast",
        params={"region_id": 1, "horizon": 6},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["indicator"] == "ndvi"
    assert body["model"] == "prophet"
    assert body["horizon_steps"] == 6
    assert len(body["points"]) == 6
    first = body["points"][0]
    assert {"date", "yhat", "yhat_lower", "yhat_upper"} <= first.keys()
    assert 0 <= first["yhat"] <= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forecast_api_horizon_bounds(client) -> None:
    """horizon out of [1,24] is rejected by FastAPI validation."""
    response = await client.get(
        "/api/v1/prediction/ndvi-forecast",
        params={"region_id": 1, "horizon": 999},
    )
    assert response.status_code == 422

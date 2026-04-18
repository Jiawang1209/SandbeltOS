"""Tests for rag.live_metrics.fetch_snapshot (services mocked out)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _patch_async_session():
    """Helper: patches async_session to yield a dummy session via `async with`."""
    sess = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=sess)
    cm.__aexit__ = AsyncMock(return_value=None)
    return patch("rag.live_metrics.async_session", return_value=cm)


@pytest.mark.asyncio
async def test_fetch_snapshot_merges_all_sources() -> None:
    from rag import live_metrics

    with (
        _patch_async_session(),
        patch.object(live_metrics.ecological_svc, "get_ndvi_fvc_latest",
                     AsyncMock(return_value={"time": "2026-04-01T00:00:00", "ndvi": 0.38, "fvc": 42})),
        patch.object(live_metrics.ecological_svc, "get_risk_latest",
                     AsyncMock(return_value={"time": "2026-04-01T00:00:00", "level": 2, "score": 0.55})),
        patch.object(live_metrics.ecological_svc, "get_weather_latest",
                     AsyncMock(return_value={"time": "2026-04-01T00:00:00", "wind_speed": 3.2, "soil_moisture": 18})),
        patch.object(live_metrics.ecological_svc, "get_landcover_latest",
                     AsyncMock(return_value={"year": 2024, "grassland": 60})),
        patch.object(live_metrics.ecological_svc, "get_alerts_latest",
                     AsyncMock(return_value=[{"id": 1, "severity": "high", "message": "dust"}])),
    ):
        snap = await live_metrics.fetch_snapshot("horqin")

    assert snap["region"] == "horqin"
    assert snap["region_id"] == 1
    assert snap["ndvi"] == 0.38
    assert snap["fvc"] == 42
    assert snap["risk_level"] == 2
    assert snap["wind_speed"] == 3.2
    assert snap["soil_moisture"] == 18
    assert snap["last_alert"]["severity"] == "high"
    assert snap["landcover"]["grassland"] == 60


@pytest.mark.asyncio
async def test_fetch_snapshot_handles_empty_returns() -> None:
    from rag import live_metrics

    with (
        _patch_async_session(),
        patch.object(live_metrics.ecological_svc, "get_ndvi_fvc_latest", AsyncMock(return_value=None)),
        patch.object(live_metrics.ecological_svc, "get_risk_latest", AsyncMock(return_value=None)),
        patch.object(live_metrics.ecological_svc, "get_weather_latest", AsyncMock(return_value=None)),
        patch.object(live_metrics.ecological_svc, "get_landcover_latest", AsyncMock(return_value={})),
        patch.object(live_metrics.ecological_svc, "get_alerts_latest", AsyncMock(return_value=[])),
    ):
        snap = await live_metrics.fetch_snapshot("hunshandake")

    assert snap["region_id"] == 2
    assert snap["ndvi"] is None
    assert snap["risk_level"] is None
    assert snap["last_alert"] is None


@pytest.mark.asyncio
async def test_fetch_snapshot_unknown_region() -> None:
    from rag import live_metrics

    snap = await live_metrics.fetch_snapshot("gobi")
    assert "error" in snap
    assert snap["region"] == "gobi"

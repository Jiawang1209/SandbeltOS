"""Aggregate live sensor metrics for a region by calling services in parallel.

Called by the chat endpoint when the query router flags `needs_live_data`.
Translates the RAG-level string region ID (e.g. "horqin") to the DB
integer `regions.id`, then fans out across five service calls and merges
the results into a single flat dict for the prompt builder.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.database import async_session
from app.services import ecological as ecological_svc

# RAG-level region alias → DB regions.id
REGION_ID_MAP: dict[str, int] = {
    "horqin": 1,
    "hunshandake": 2,
}


async def fetch_snapshot(region: str) -> dict[str, Any]:
    """Fan-out latest ecological metrics for `region`, merge to a flat dict.

    Returns the shape consumed by prompt_templates.build_eco_prompt. Missing
    values are left as None rather than raising, because an incomplete
    snapshot is still useful to the LLM.
    """
    region_id = REGION_ID_MAP.get(region)
    if region_id is None:
        return {"region": region, "error": f"unknown region: {region}"}

    # Each concurrent query needs its own AsyncSession — a single session
    # cannot serve parallel `asyncio.gather` calls (IllegalStateChangeError).
    async def _run(fn, *args, **kwargs):
        async with async_session() as sess:
            return await fn(region_id, sess, *args, **kwargs)

    ndvi_fvc, risk, weather, landcover, alerts = await asyncio.gather(
        _run(ecological_svc.get_ndvi_fvc_latest),
        _run(ecological_svc.get_risk_latest),
        _run(ecological_svc.get_weather_latest),
        _run(ecological_svc.get_landcover_latest),
        _run(ecological_svc.get_alerts_latest, limit=1),
    )

    ndvi_fvc = ndvi_fvc or {}
    risk = risk or {}
    weather = weather or {}
    return {
        "region": region,
        "region_id": region_id,
        "timestamp": ndvi_fvc.get("time") or weather.get("time"),
        "ndvi": ndvi_fvc.get("ndvi"),
        "fvc": ndvi_fvc.get("fvc"),
        "risk_level": risk.get("level"),
        "risk_score": risk.get("score"),
        "wind_speed": weather.get("wind_speed"),
        "soil_moisture": weather.get("soil_moisture"),
        "landcover": landcover,
        "last_alert": alerts[0] if alerts else None,
    }

"""Pure service functions for ecological data access.

Extracted from `api/v1/ecological.py` so that non-HTTP callers (e.g.
`rag.live_metrics`) can reuse the same queries. Functions return plain
dicts matching the existing endpoint response shape exactly — the router
layer is now a thin delegator.

Convention: when a region doesn't exist, services return a dict with
`{"error": "Region X not found"}` (matches the legacy timeseries/current-
status behavior). `get_landcover` raises `LookupError`; the router
translates it to HTTP 404 for backward compatibility.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_LANDCOVER_DIR = Path(__file__).resolve().parents[2] / "data" / "landcover"


async def _fetch_region(region_id: int, db: AsyncSession) -> dict | None:
    result = await db.execute(
        text("SELECT id, name, level, area_km2 FROM regions WHERE id = :id"),
        {"id": region_id},
    )
    row = result.fetchone()
    if row is None:
        return None
    return {"id": row[0], "name": row[1], "level": row[2], "area_km2": row[3]}


async def get_timeseries(
    region_id: int,
    indicator: str,
    start_date: str,
    end_date: str,
    db: AsyncSession,
) -> dict[str, Any]:
    region = await _fetch_region(region_id, db)
    if region is None:
        return {"error": f"Region {region_id} not found"}

    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)

    result = await db.execute(
        text(
            """
            SELECT time, value, source
            FROM eco_indicators
            WHERE region_id = :region_id
              AND indicator = :indicator
              AND time >= :start_date
              AND time <= :end_date
            ORDER BY time
            """
        ),
        {
            "region_id": region_id,
            "indicator": indicator,
            "start_date": start_dt,
            "end_date": end_dt,
        },
    )
    data = [
        {"time": row[0].isoformat(), "value": row[1], "source": row[2]}
        for row in result.fetchall()
    ]
    return {"region": region, "indicator": indicator, "data": data}


async def get_weather(
    region_id: int,
    start_date: str,
    end_date: str,
    db: AsyncSession,
) -> dict[str, Any]:
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)

    result = await db.execute(
        text(
            """
            SELECT time, precipitation, temperature, wind_speed,
                   wind_direction, evapotranspiration, soil_moisture
            FROM weather_data
            WHERE region_id = :region_id
              AND time >= :start_date
              AND time <= :end_date
            ORDER BY time
            """
        ),
        {"region_id": region_id, "start_date": start_dt, "end_date": end_dt},
    )
    data = [
        {
            "time": row[0].isoformat(),
            "precipitation": row[1],
            "temperature": row[2],
            "wind_speed": row[3],
            "wind_direction": row[4],
            "evapotranspiration": row[5],
            "soil_moisture": row[6],
        }
        for row in result.fetchall()
    ]
    return {"region_id": region_id, "data": data}


async def get_current_status(region_id: int, db: AsyncSession) -> dict[str, Any]:
    region = await _fetch_region(region_id, db)
    if region is None:
        return {"error": f"Region {region_id} not found"}

    risk_result = await db.execute(
        text(
            """
            SELECT time, risk_level, risk_score, wind_erosion_modulus,
                   sand_fixation_amount, factors
            FROM desertification_risk
            WHERE region_id = :rid
            ORDER BY time DESC LIMIT 1
            """
        ),
        {"rid": region_id},
    )
    risk_row = risk_result.fetchone()
    latest = None
    if risk_row is not None:
        latest = {
            "time": risk_row[0].isoformat(),
            "risk_level": risk_row[1],
            "risk_score": risk_row[2],
            "wind_erosion_modulus": risk_row[3],
            "sand_fixation_amount": risk_row[4],
            "factors": risk_row[5],
        }

    alerts_result = await db.execute(
        text(
            """
            SELECT id, created_at, alert_type, severity, message
            FROM alerts
            WHERE region_id = :rid
            ORDER BY created_at DESC LIMIT 5
            """
        ),
        {"rid": region_id},
    )
    alerts = [
        {
            "id": row[0],
            "created_at": row[1].isoformat(),
            "alert_type": row[2],
            "severity": row[3],
            "message": row[4],
        }
        for row in alerts_result.fetchall()
    ]
    return {"region": region, "latest": latest, "alerts": alerts}


async def get_risk_timeseries(
    region_id: int,
    start_date: str,
    end_date: str,
    db: AsyncSession,
) -> dict[str, Any]:
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)

    result = await db.execute(
        text(
            """
            SELECT time, risk_level, risk_score,
                   wind_erosion_modulus, sand_fixation_amount, factors
            FROM desertification_risk
            WHERE region_id = :rid
              AND time >= :start AND time <= :end
            ORDER BY time
            """
        ),
        {"rid": region_id, "start": start_dt, "end": end_dt},
    )
    data = [
        {
            "time": row[0].isoformat(),
            "risk_level": row[1],
            "risk_score": row[2],
            "wind_erosion_modulus": row[3],
            "sand_fixation_amount": row[4],
            "factors": row[5],
        }
        for row in result.fetchall()
    ]
    return {"region_id": region_id, "data": data}


async def get_landcover(region_id: int, db: AsyncSession) -> dict[str, Any]:
    """Raises LookupError if region missing; router translates to 404."""
    region = await _fetch_region(region_id, db)
    if region is None:
        raise LookupError(f"Region {region_id} not found")

    path = _LANDCOVER_DIR / f"{region_id}.json"
    if not path.exists():
        return {"region": region, "series": []}

    payload = json.loads(path.read_text())
    return {"region": region, "series": payload.get("series", [])}


async def get_ndvi_fvc_latest(region_id: int, db: AsyncSession) -> dict[str, Any] | None:
    """Most recent NDVI/FVC sample for a region. None if nothing ingested."""
    result = await db.execute(
        text(
            """
            SELECT time, indicator, value
            FROM eco_indicators
            WHERE region_id = :rid AND indicator IN ('ndvi', 'fvc')
            ORDER BY time DESC LIMIT 2
            """
        ),
        {"rid": region_id},
    )
    rows = result.fetchall()
    if not rows:
        return None
    latest: dict[str, Any] = {"time": rows[0][0].isoformat()}
    for row in rows:
        latest[row[1]] = row[2]
    return latest


async def get_risk_latest(region_id: int, db: AsyncSession) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT time, risk_level, risk_score
            FROM desertification_risk
            WHERE region_id = :rid
            ORDER BY time DESC LIMIT 1
            """
        ),
        {"rid": region_id},
    )
    row = result.fetchone()
    if row is None:
        return None
    return {"time": row[0].isoformat(), "level": row[1], "score": row[2]}


async def get_weather_latest(region_id: int, db: AsyncSession) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT time, precipitation, temperature, wind_speed, soil_moisture
            FROM weather_data
            WHERE region_id = :rid
            ORDER BY time DESC LIMIT 1
            """
        ),
        {"rid": region_id},
    )
    row = result.fetchone()
    if row is None:
        return None
    return {
        "time": row[0].isoformat(),
        "precipitation": row[1],
        "temperature": row[2],
        "wind_speed": row[3],
        "soil_moisture": row[4],
    }


async def get_landcover_latest(region_id: int, db: AsyncSession) -> dict[str, Any]:
    """Most recent year's landcover composition (reads cached JSON)."""
    path = _LANDCOVER_DIR / f"{region_id}.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    series = payload.get("series") or []
    if not series:
        return {}
    return series[-1]


async def get_alerts_latest(
    region_id: int, db: AsyncSession, limit: int = 1
) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            SELECT id, created_at, alert_type, severity, message
            FROM alerts
            WHERE region_id = :rid
            ORDER BY created_at DESC LIMIT :limit
            """
        ),
        {"rid": region_id, "limit": limit},
    )
    return [
        {
            "id": row[0],
            "created_at": row[1].isoformat(),
            "alert_type": row[2],
            "severity": row[3],
            "message": row[4],
        }
        for row in result.fetchall()
    ]


async def list_alerts(
    region_id: int | None,
    severity: str | None,
    limit: int,
    db: AsyncSession,
) -> dict[str, Any]:
    clauses = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if region_id is not None:
        clauses.append("region_id = :rid")
        params["rid"] = region_id
    if severity:
        clauses.append("severity = :sev")
        params["sev"] = severity

    result = await db.execute(
        text(
            f"""
            SELECT a.id, a.created_at, a.region_id, r.name,
                   a.alert_type, a.severity, a.message
            FROM alerts a JOIN regions r ON r.id = a.region_id
            WHERE {' AND '.join(clauses)}
            ORDER BY a.created_at DESC LIMIT :limit
            """
        ),
        params,
    )
    data = [
        {
            "id": row[0],
            "created_at": row[1].isoformat(),
            "region_id": row[2],
            "region_name": row[3],
            "alert_type": row[4],
            "severity": row[5],
            "message": row[6],
        }
        for row in result.fetchall()
    ]
    return {"data": data}

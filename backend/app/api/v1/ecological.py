from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/timeseries")
async def get_timeseries(
    region_id: int = Query(1, description="Region ID"),
    indicator: str = Query("ndvi", description="Indicator: ndvi, evi, lst, soil_moisture"),
    start_date: str = Query("2020-01-01", description="Start date YYYY-MM-DD"),
    end_date: str = Query("2024-12-31", description="End date YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """Get ecological indicator timeseries for a region."""
    # Fetch region info
    region_result = await db.execute(
        text("SELECT id, name, level, area_km2 FROM regions WHERE id = :id"),
        {"id": region_id},
    )
    region_row = region_result.fetchone()
    if region_row is None:
        return {"error": f"Region {region_id} not found"}

    region = {
        "id": region_row[0],
        "name": region_row[1],
        "level": region_row[2],
        "area_km2": region_row[3],
    }

    # Parse date strings to datetime objects (asyncpg requires native Python types)
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)

    # Fetch timeseries data
    result = await db.execute(
        text("""
            SELECT time, value, source
            FROM eco_indicators
            WHERE region_id = :region_id
              AND indicator = :indicator
              AND time >= :start_date
              AND time <= :end_date
            ORDER BY time
        """),
        {
            "region_id": region_id,
            "indicator": indicator,
            "start_date": start_dt,
            "end_date": end_dt,
        },
    )
    rows = result.fetchall()

    data = [
        {
            "time": row[0].isoformat(),
            "value": row[1],
            "source": row[2],
        }
        for row in rows
    ]

    return {
        "region": region,
        "indicator": indicator,
        "data": data,
    }


@router.get("/weather")
async def get_weather(
    region_id: int = Query(1, description="Region ID"),
    start_date: str = Query("2020-01-01", description="Start date YYYY-MM-DD"),
    end_date: str = Query("2024-12-31", description="End date YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """Get weather timeseries for a region."""
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)

    result = await db.execute(
        text("""
            SELECT time, precipitation, temperature, wind_speed,
                   wind_direction, evapotranspiration, soil_moisture
            FROM weather_data
            WHERE region_id = :region_id
              AND time >= :start_date
              AND time <= :end_date
            ORDER BY time
        """),
        {"region_id": region_id, "start_date": start_dt, "end_date": end_dt},
    )
    rows = result.fetchall()

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
        for row in rows
    ]

    return {"region_id": region_id, "data": data}

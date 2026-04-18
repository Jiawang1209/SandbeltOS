"""Thin HTTP wrappers; query logic lives in app.services.ecological."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import ecological as svc

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
    return await svc.get_timeseries(region_id, indicator, start_date, end_date, db)


@router.get("/weather")
async def get_weather(
    region_id: int = Query(1, description="Region ID"),
    start_date: str = Query("2020-01-01", description="Start date YYYY-MM-DD"),
    end_date: str = Query("2024-12-31", description="End date YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """Get weather timeseries for a region."""
    return await svc.get_weather(region_id, start_date, end_date, db)


@router.get("/current-status")
async def get_current_status(
    region_id: int = Query(1, description="Region ID"),
    db: AsyncSession = Depends(get_db),
):
    """Latest indicator snapshot + active alerts for a region."""
    return await svc.get_current_status(region_id, db)


@router.get("/risk-timeseries")
async def get_risk_timeseries(
    region_id: int = Query(1, description="Region ID"),
    start_date: str = Query("2015-01-01"),
    end_date: str = Query("2025-12-31"),
    db: AsyncSession = Depends(get_db),
):
    """Desertification risk timeseries for a region."""
    return await svc.get_risk_timeseries(region_id, start_date, end_date, db)


@router.get("/landcover")
async def get_landcover(
    region_id: int = Query(..., description="Subregion id"),
    db: AsyncSession = Depends(get_db),
):
    """Annual MCD12Q1 land-cover composition for a sandy land."""
    try:
        return await svc.get_landcover(region_id, db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/alerts")
async def list_alerts(
    region_id: int | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Recent alerts, optionally filtered by region or severity."""
    return await svc.list_alerts(region_id, severity, limit, db)

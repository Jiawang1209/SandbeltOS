from pydantic import BaseModel
from datetime import datetime


class HealthResponse(BaseModel):
    status: str
    version: str


class RegionBase(BaseModel):
    id: int
    name: str
    level: str | None = None
    area_km2: float | None = None


class TimeseriesPoint(BaseModel):
    time: datetime
    value: float
    source: str | None = None


class TimeseriesResponse(BaseModel):
    region: RegionBase
    indicator: str
    data: list[TimeseriesPoint]


class CurrentStatusResponse(BaseModel):
    region_id: int
    as_of: datetime | None = None
    ndvi_mean: float | None = None
    fvc: float | None = None
    soil_moisture: float | None = None
    risk_level: int | None = None
    risk_score: float | None = None
    wind_erosion_modulus: float | None = None
    sand_fixation_amount: float | None = None
    carbon_density_gc_m2: float | None = None
    alerts: list[dict] = []

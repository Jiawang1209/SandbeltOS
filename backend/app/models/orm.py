from sqlalchemy import Column, Integer, String, Float, SmallInteger, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from geoalchemy2 import Geometry

from app.database import Base


class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    level = Column(String(20))
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))
    area_km2 = Column(Float)
    created_at = Column(TIMESTAMP(timezone=True), server_default="now()")


class EcoIndicator(Base):
    __tablename__ = "eco_indicators"

    time = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), primary_key=True)
    indicator = Column(String(50), primary_key=True, nullable=False)
    value = Column(Float, nullable=False)
    source = Column(String(30))
    resolution = Column(String(20))
    quality = Column(SmallInteger, default=1)


class WeatherData(Base):
    __tablename__ = "weather_data"

    time = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), primary_key=True)
    precipitation = Column(Float)
    wind_speed = Column(Float)
    wind_direction = Column(Float)
    temperature = Column(Float)
    evapotranspiration = Column(Float)
    soil_moisture = Column(Float)


class DesertificationRisk(Base):
    __tablename__ = "desertification_risk"

    time = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), primary_key=True)
    risk_level = Column(SmallInteger)
    risk_score = Column(Float)
    wind_erosion_modulus = Column(Float)
    sand_fixation_amount = Column(Float)
    factors = Column(JSONB)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default="now()")
    region_id = Column(Integer, ForeignKey("regions.id"))
    alert_type = Column(String(50))
    severity = Column(String(20))
    message = Column(Text)
    is_read = Column(Boolean, default=False)

"""Seed synthetic data for 浑善达克沙地 (Hunshandake Sandy Land), region_id=2."""

import asyncio
import numpy as np
import pandas as pd
from sqlalchemy import text

from app.database import async_session
from app.services.data_writer import write_eco_indicators, write_weather_data


REGION_ID = 2


def generate_ndvi(start_date: str, end_date: str, seed: int = 88) -> pd.DataFrame:
    """Hunshandake: lower NDVI than Horqin, more grassland-steppe character."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start_date, end_date, freq="16D", tz="UTC")
    n = len(dates)

    doy = dates.dayofyear.values
    seasonal = np.sin(2 * np.pi * (doy - 80) / 365)

    ndvi_mean = 0.12 + 0.13 * seasonal + rng.normal(0, 0.02, n)
    ndvi_mean = np.clip(ndvi_mean, 0.02, 0.42)

    year_offset = (dates.year - 2020).values
    ndvi_mean = ndvi_mean + year_offset * 0.004

    evi_mean = ndvi_mean * 0.82 + rng.normal(0, 0.01, n)

    return pd.DataFrame({
        "time": dates,
        "ndvi_mean": np.round(ndvi_mean, 4),
        "evi_mean": np.round(np.clip(evi_mean, 0.01, 0.38), 4),
    })


def generate_weather(start_date: str, end_date: str, seed: int = 88) -> pd.DataFrame:
    """Hunshandake: colder winters, drier, strong spring winds."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start_date, end_date, freq="D", tz="UTC")
    n = len(dates)

    doy = dates.dayofyear.values
    seasonal = np.sin(2 * np.pi * (doy - 80) / 365)

    temperature = 2 + 23 * seasonal + rng.normal(0, 3, n)
    precip_base = np.maximum(0, 1.2 * seasonal + 0.3)
    precipitation = rng.exponential(precip_base) * rng.binomial(1, 0.25 + 0.15 * seasonal, n)

    spring_factor = np.exp(-((doy - 95) ** 2) / 1800)
    wind_speed = 3.5 + 4.5 * spring_factor + rng.normal(0, 1.5, n)
    wind_speed = np.maximum(0.5, wind_speed)
    wind_direction = 310 + 35 * seasonal + rng.normal(0, 40, n)
    wind_direction = wind_direction % 360

    evapotranspiration = np.maximum(0, 1.6 + 3.6 * seasonal + rng.normal(0, 0.5, n))
    soil_moisture = 0.07 + 0.035 * (-seasonal) + 0.002 * precipitation + rng.normal(0, 0.01, n)
    soil_moisture = np.clip(soil_moisture, 0.02, 0.22)

    return pd.DataFrame({
        "date": dates,
        "precipitation": np.round(precipitation, 2),
        "temperature": np.round(temperature, 1),
        "wind_speed": np.round(wind_speed, 1),
        "wind_direction": np.round(wind_direction, 1),
        "evapotranspiration": np.round(evapotranspiration, 2),
        "soil_moisture": np.round(soil_moisture, 4),
    })


async def seed() -> None:
    print("=== Seeding 浑善达克沙地 (Hunshandake) ===\n")

    async with async_session() as session:
        ndvi_df = generate_ndvi("2020-01-01", "2024-12-31")
        print(f"Generated {len(ndvi_df)} NDVI records")

        ndvi_count = await write_eco_indicators(
            session, ndvi_df, REGION_ID, "ndvi", source="MODIS_synthetic", resolution="500m"
        )
        print(f"Inserted {ndvi_count} NDVI records")

        evi_df = ndvi_df[["time", "evi_mean"]].copy()
        evi_count = await write_eco_indicators(
            session, evi_df, REGION_ID, "evi", source="MODIS_synthetic", resolution="500m"
        )
        print(f"Inserted {evi_count} EVI records")

        weather_df = generate_weather("2020-01-01", "2024-12-31")
        print(f"Generated {len(weather_df)} weather records")

        weather_count = await write_weather_data(session, weather_df, REGION_ID)
        print(f"Inserted {weather_count} weather records")

        # Verify
        for ind in ["ndvi", "evi"]:
            result = await session.execute(
                text("SELECT count(*) FROM eco_indicators WHERE region_id = :rid AND indicator = :ind"),
                {"rid": REGION_ID, "ind": ind},
            )
            print(f"  eco_indicators ({ind}): {result.scalar()}")

        result = await session.execute(
            text("SELECT count(*) FROM weather_data WHERE region_id = :rid"),
            {"rid": REGION_ID},
        )
        print(f"  weather_data: {result.scalar()}")

    print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(seed())

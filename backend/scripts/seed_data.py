"""
Seed the database with synthetic data for development and testing.
Generates realistic NDVI timeseries + weather data for Horqin Sandy Land (2020-2024).

Usage:
    conda activate sandbelt
    cd backend
    python -m scripts.seed_data
"""

import asyncio
import numpy as np
import pandas as pd
from sqlalchemy import text

from app.database import async_session
from app.services.data_writer import write_eco_indicators, write_weather_data
from app.services.era5_service import generate_synthetic_weather


REGION_ID = 1


def generate_synthetic_ndvi(start_date: str, end_date: str, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic 16-day MODIS NDVI data mimicking Horqin Sandy Land patterns.
    NDVI range: 0.05 (winter bare) to 0.45 (summer peak).
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start_date, end_date, freq="16D", tz="UTC")
    n = len(dates)

    doy = dates.dayofyear.values
    seasonal = np.sin(2 * np.pi * (doy - 80) / 365)

    # NDVI: low in winter (~0.05), peak in summer (~0.40)
    ndvi_mean = 0.15 + 0.15 * seasonal + rng.normal(0, 0.02, n)
    ndvi_mean = np.clip(ndvi_mean, 0.02, 0.50)

    # Add slight upward trend (reforestation effect)
    year_offset = (dates.year - 2020).values
    ndvi_mean = ndvi_mean + year_offset * 0.005

    ndvi_min = ndvi_mean - rng.uniform(0.03, 0.08, n)
    ndvi_max = ndvi_mean + rng.uniform(0.03, 0.08, n)
    evi_mean = ndvi_mean * 0.85 + rng.normal(0, 0.01, n)

    return pd.DataFrame(
        {
            "time": dates,
            "ndvi_mean": np.round(ndvi_mean, 4),
            "ndvi_min": np.round(np.clip(ndvi_min, 0.01, 0.50), 4),
            "ndvi_max": np.round(np.clip(ndvi_max, 0.02, 0.55), 4),
            "evi_mean": np.round(np.clip(evi_mean, 0.01, 0.45), 4),
        }
    )


async def seed() -> None:
    print("=== SandbeltOS Data Seeding ===\n")

    async with async_session() as session:
        # Check region exists
        result = await session.execute(
            text("SELECT id, name FROM regions WHERE id = :id"), {"id": REGION_ID}
        )
        region = result.fetchone()
        if region is None:
            print(f"Region {REGION_ID} not found. Creating...")
            await session.execute(
                text("""
                    INSERT INTO regions (id, name, level, area_km2)
                    VALUES (:id, :name, :level, :area)
                """),
                {"id": REGION_ID, "name": "科尔沁沙地", "level": "subregion", "area": 42300.0},
            )
            await session.commit()
            print("  Created region: 科尔沁沙地")
        else:
            print(f"  Region found: {region[1]}")

        # Ensure tables exist
        for table in ["eco_indicators", "weather_data"]:
            result = await session.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = :table
                    )
                """),
                {"table": table},
            )
            exists = result.scalar()
            if not exists:
                print(f"  ERROR: Table '{table}' does not exist. Run sql/init.sql first.")
                return

        # Generate and write NDVI data
        print("\n[1/3] Generating synthetic NDVI data (2020-2024)...")
        ndvi_df = generate_synthetic_ndvi("2020-01-01", "2024-12-31")
        print(f"  Generated {len(ndvi_df)} NDVI records")

        ndvi_count = await write_eco_indicators(
            session, ndvi_df, REGION_ID, "ndvi", source="MODIS_synthetic", resolution="500m"
        )
        print(f"  Inserted {ndvi_count} NDVI records into eco_indicators")

        # Write EVI as separate indicator
        evi_df = ndvi_df[["time", "evi_mean"]].copy()
        evi_count = await write_eco_indicators(
            session, evi_df, REGION_ID, "evi", source="MODIS_synthetic", resolution="500m"
        )
        print(f"  Inserted {evi_count} EVI records into eco_indicators")

        # Generate and write weather data
        print("\n[2/3] Generating synthetic weather data (2020-2024)...")
        weather_df = generate_synthetic_weather("2020-01-01", "2024-12-31")
        print(f"  Generated {len(weather_df)} daily weather records")

        weather_count = await write_weather_data(session, weather_df, REGION_ID)
        print(f"  Inserted {weather_count} weather records into weather_data")

        # Verify
        print("\n[3/3] Verifying...")
        for table, indicator in [("eco_indicators", "ndvi"), ("eco_indicators", "evi")]:
            result = await session.execute(
                text(f"SELECT count(*) FROM {table} WHERE region_id = :rid AND indicator = :ind"),
                {"rid": REGION_ID, "ind": indicator},
            )
            print(f"  {table} ({indicator}): {result.scalar()} records")

        result = await session.execute(
            text("SELECT count(*) FROM weather_data WHERE region_id = :rid"),
            {"rid": REGION_ID},
        )
        print(f"  weather_data: {result.scalar()} records")

    print("\n=== Seeding complete ===")


if __name__ == "__main__":
    asyncio.run(seed())

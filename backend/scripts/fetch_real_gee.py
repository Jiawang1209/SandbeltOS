"""
Fetch real MODIS NDVI/EVI data from GEE and replace synthetic data.
Requires: earthengine-api authenticated + project registered.

Usage:
    cd backend
    DATABASE_URL="postgresql+asyncpg://sandbelt@localhost:5432/sandbelt_db" \
    python -m scripts.fetch_real_gee
"""

import asyncio
import ee
import pandas as pd
from sqlalchemy import text

from app.database import async_session
from app.services.data_writer import write_eco_indicators


GEE_PROJECT = "ee-yueliu19921209"

REGIONS = {
    1: {
        "name": "科尔沁沙地",
        "bbox": [119, 42, 124, 45],
    },
    2: {
        "name": "浑善达克沙地",
        "bbox": [112, 42, 116.5, 43.5],
    },
}


def fetch_modis_ndvi_evi(bbox: list[float], start: str, end: str) -> pd.DataFrame:
    """Fetch MODIS MOD13A1 NDVI+EVI from GEE, serially per image to avoid concurrent-aggregation rate limits."""
    import time

    ee.Initialize(project=GEE_PROJECT)
    roi = ee.Geometry.Rectangle(bbox)

    start_year = int(start[:4])
    end_year = int(end[:4])

    all_rows: list[dict] = []

    for year in range(start_year, end_year + 1):
        y_start = f"{year}-01-01"
        y_end = f"{year}-12-31"

        collection = (
            ee.ImageCollection("MODIS/061/MOD13A1")
            .filterDate(y_start, y_end)
            .filterBounds(roi)
            .select(["NDVI", "EVI"])
        )

        # Materialize dates once (one cheap getInfo); then reduce per-image serially.
        try:
            print(f"  {year}: listing dates...", end=" ", flush=True)
            dates = collection.aggregate_array("system:time_start").getInfo()
            print(f"{len(dates)} images")
        except Exception as e:
            print(f"FAILED to list ({e})")
            continue

        year_rows: list[dict] = []
        for i, ts_ms in enumerate(dates, start=1):
            date_str = pd.Timestamp(ts_ms, unit="ms", tz="UTC").strftime("%Y-%m-%d")

            for attempt in range(4):
                try:
                    image = collection.filter(
                        ee.Filter.eq("system:time_start", ts_ms)
                    ).first()
                    ndvi = image.select("NDVI").multiply(0.0001)
                    evi = image.select("EVI").multiply(0.0001)
                    ndvi_stats = ndvi.reduceRegion(
                        reducer=ee.Reducer.mean()
                        .combine(ee.Reducer.min(), sharedInputs=True)
                        .combine(ee.Reducer.max(), sharedInputs=True),
                        geometry=roi,
                        scale=500,
                        maxPixels=1e13,
                    )
                    evi_stats = evi.reduceRegion(
                        reducer=ee.Reducer.mean()
                        .combine(ee.Reducer.min(), sharedInputs=True)
                        .combine(ee.Reducer.max(), sharedInputs=True),
                        geometry=roi,
                        scale=500,
                        maxPixels=1e13,
                    )
                    props = ndvi_stats.combine(evi_stats).getInfo()
                    year_rows.append({
                        "time": pd.Timestamp(date_str, tz="UTC"),
                        "ndvi_mean": props.get("NDVI_mean"),
                        "ndvi_min": props.get("NDVI_min"),
                        "ndvi_max": props.get("NDVI_max"),
                        "evi_mean": props.get("EVI_mean"),
                    })
                    break
                except Exception as e:
                    msg = str(e)
                    wait = 5 * (attempt + 1)
                    print(f"    {date_str}: {msg[:80]} — retry in {wait}s", flush=True)
                    time.sleep(wait)
            else:
                print(f"    {date_str}: SKIPPED after retries", flush=True)

            time.sleep(0.4)  # gentle pacing between serial calls

        all_rows.extend(year_rows)
        print(f"  {year}: +{len(year_rows)} rows (running total {len(all_rows)})")
        time.sleep(2)

    return pd.DataFrame(all_rows)


async def main() -> None:
    print("=== Fetching Real MODIS NDVI/EVI from GEE ===\n")

    async with async_session() as session:
        for region_id, info in REGIONS.items():
            print(f"[{info['name']}] (region_id={region_id})")

            # Clear prior synthetic + GEE rows so re-runs stay consistent (no UNIQUE constraint on table)
            await session.execute(
                text(
                    "DELETE FROM eco_indicators WHERE region_id = :rid "
                    "AND source IN ('MODIS_synthetic', 'MODIS_GEE') "
                    "AND indicator IN ('ndvi', 'evi')"
                ),
                {"rid": region_id},
            )
            await session.commit()
            print("  Cleared prior NDVI/EVI rows (synthetic + GEE)")

            # Fetch real data
            df = fetch_modis_ndvi_evi(info["bbox"], "2020-01-01", "2024-12-31")
            print(f"  Fetched {len(df)} records from GEE")

            if len(df) == 0:
                print("  WARNING: No data returned, skipping")
                continue

            # Write NDVI
            ndvi_count = await write_eco_indicators(
                session, df, region_id, "ndvi", source="MODIS_GEE", resolution="500m"
            )
            print(f"  Inserted {ndvi_count} NDVI records")

            # Write EVI
            evi_df = df[["time", "evi_mean"]].copy()
            evi_count = await write_eco_indicators(
                session, evi_df, region_id, "evi", source="MODIS_GEE", resolution="500m"
            )
            print(f"  Inserted {evi_count} EVI records")

        # Verify
        print("\n=== Verification ===")
        for region_id, info in REGIONS.items():
            for ind in ["ndvi", "evi"]:
                result = await session.execute(
                    text("SELECT count(*), source FROM eco_indicators WHERE region_id = :rid AND indicator = :ind GROUP BY source"),
                    {"rid": region_id, "ind": ind},
                )
                for row in result.fetchall():
                    print(f"  {info['name']} {ind}: {row[0]} records ({row[1]})")

    print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())

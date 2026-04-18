"""
Simplified NDVI/EVI fetch — mean only, 1000m scale to avoid GEE rate limits.
Fills in years that fetch_all_gee.py missed.

Usage:
    cd backend
    https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 \
    conda run -n sandbelt python -m scripts.fetch_ndvi_simple
"""

import asyncio
import time

import ee
import pandas as pd
from sqlalchemy import text

from app.database import async_session

GEE_PROJECT = "ee-yueliu19921209"

REGIONS = {
    1: {"name": "科尔沁沙地", "bbox": [119, 42, 124, 45]},
    2: {"name": "浑善达克沙地", "bbox": [112, 42, 116.5, 43.5]},
}

START_YEAR = 2000
END_YEAR = 2026


def fetch_ndvi_year(bbox: list[float], year: int) -> list[dict]:
    """Simplified: mean only, 1000m scale, lighter on GEE quota."""
    roi = ee.Geometry.Rectangle(bbox)
    col = (
        ee.ImageCollection("MODIS/061/MOD13A1")
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .filterBounds(roi)
        .select(["NDVI", "EVI"])
    )

    def extract(image: ee.Image) -> ee.Feature:
        d = image.date().format("YYYY-MM-dd")
        ndvi = image.select("NDVI").multiply(0.0001)
        evi = image.select("EVI").multiply(0.0001)
        # Mean only, 1000m scale — much lighter than mean+min+max at 500m
        ns = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=roi, scale=1000, maxPixels=1e13,
        )
        es = evi.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=roi, scale=1000, maxPixels=1e13,
        )
        return ee.Feature(None, ns.combine(es).set("date", d))

    for attempt in range(5):
        try:
            result = col.map(extract).getInfo()
            rows = []
            for f in result["features"]:
                p = f["properties"]
                rows.append({
                    "time": pd.Timestamp(p["date"], tz="UTC"),
                    "ndvi_mean": p.get("NDVI"),
                    "evi_mean": p.get("EVI"),
                })
            return rows
        except Exception as e:
            wait = 20 * (attempt + 1)
            print(f"    retry {attempt + 1}/5 in {wait}s ({e})", flush=True)
            time.sleep(wait)
    return []


async def main() -> None:
    ee.Initialize(project=GEE_PROJECT)
    print("GEE initialized\n", flush=True)

    async with async_session() as session:
        for region_id, info in REGIONS.items():
            name = info["name"]
            bbox = info["bbox"]

            # Find which years already have NDVI data
            result = await session.execute(
                text("""
                    SELECT DISTINCT EXTRACT(YEAR FROM time)::int AS yr
                    FROM eco_indicators
                    WHERE region_id = :rid AND indicator = 'ndvi' AND source = 'MODIS_GEE'
                """),
                {"rid": region_id},
            )
            existing_years = {row[0] for row in result.fetchall()}

            missing_years = [y for y in range(START_YEAR, END_YEAR + 1) if y not in existing_years]
            if not missing_years:
                print(f"[{name}] All years present, skipping\n", flush=True)
                continue

            print(f"[{name}] Missing NDVI years: {missing_years}\n", flush=True)

            total_ndvi = 0
            total_evi = 0

            for year in missing_years:
                print(f"  {year}...", end=" ", flush=True)
                rows = fetch_ndvi_year(bbox, year)

                if not rows:
                    print("FAILED", flush=True)
                    continue

                for r in rows:
                    if r["ndvi_mean"] is not None:
                        await session.execute(
                            text("""INSERT INTO eco_indicators (time, region_id, indicator, value, source, resolution)
                                    VALUES (:t, :rid, 'ndvi', :v, 'MODIS_GEE', '1km')
                                    ON CONFLICT DO NOTHING"""),
                            {"t": r["time"], "rid": region_id, "v": float(r["ndvi_mean"])},
                        )
                        total_ndvi += 1

                    if r["evi_mean"] is not None:
                        await session.execute(
                            text("""INSERT INTO eco_indicators (time, region_id, indicator, value, source, resolution)
                                    VALUES (:t, :rid, 'evi', :v, 'MODIS_GEE', '1km')
                                    ON CONFLICT DO NOTHING"""),
                            {"t": r["time"], "rid": region_id, "v": float(r["evi_mean"])},
                        )
                        total_evi += 1

                await session.commit()
                print(f"OK ({len(rows)} images)", flush=True)
                time.sleep(5)

            print(f"\n  [{name}] Inserted: NDVI={total_ndvi} EVI={total_evi}\n", flush=True)

        # Verify
        print("=" * 50, flush=True)
        result = await session.execute(text("""
            SELECT r.name, e.indicator, e.source, count(*),
                   min(e.time)::date, max(e.time)::date
            FROM eco_indicators e JOIN regions r ON r.id = e.region_id
            GROUP BY r.name, e.indicator, e.source
            ORDER BY r.name, e.indicator
        """))
        for row in result.fetchall():
            print(f"  {row[0]:15s} {row[1]:15s} {row[2]:12s} {row[3]:5d}  ({row[4]} ~ {row[5]})", flush=True)

    print("\n=== DONE ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

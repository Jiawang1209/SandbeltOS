"""
Fetch all GEE remote sensing data: MODIS NDVI/EVI, MODIS LST, SMAP Soil Moisture.
Time range: 2000-2026 (SMAP from 2015).

Usage:
    cd backend
    https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 \
    conda run -n sandbelt python -m scripts.fetch_all_gee
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


def init_gee() -> None:
    ee.Initialize(project=GEE_PROJECT)
    print("GEE initialized\n", flush=True)


# ---------------------------------------------------------------------------
# MODIS NDVI / EVI  (MOD13A1, 16-day, 500m)
# ---------------------------------------------------------------------------

def fetch_ndvi_year(bbox: list[float], year: int) -> list[dict]:
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
        ns = ndvi.reduceRegion(
            reducer=ee.Reducer.mean()
            .combine(ee.Reducer.min(), sharedInputs=True)
            .combine(ee.Reducer.max(), sharedInputs=True),
            geometry=roi, scale=500, maxPixels=1e13,
        )
        es = evi.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=roi, scale=500, maxPixels=1e13,
        )
        return ee.Feature(None, ns.combine(es).set("date", d))

    return _fetch_with_retry(col, extract, year, "NDVI/EVI", _parse_ndvi)


def _parse_ndvi(feat: dict) -> dict:
    p = feat["properties"]
    return {
        "time": pd.Timestamp(p["date"], tz="UTC"),
        "ndvi_mean": p.get("NDVI_mean"),
        "ndvi_min": p.get("NDVI_min"),
        "ndvi_max": p.get("NDVI_max"),
        "evi_mean": p.get("EVI_mean"),
    }


# ---------------------------------------------------------------------------
# MODIS LST  (MOD11A2, 8-day, 1km)
# ---------------------------------------------------------------------------

def fetch_lst_year(bbox: list[float], year: int) -> list[dict]:
    roi = ee.Geometry.Rectangle(bbox)
    col = (
        ee.ImageCollection("MODIS/061/MOD11A2")
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .filterBounds(roi)
        .select(["LST_Day_1km"])
    )

    def extract(image: ee.Image) -> ee.Feature:
        lst_c = image.select("LST_Day_1km").multiply(0.02).subtract(273.15)
        stats = lst_c.reduceRegion(
            reducer=ee.Reducer.mean()
            .combine(ee.Reducer.min(), sharedInputs=True)
            .combine(ee.Reducer.max(), sharedInputs=True),
            geometry=roi, scale=1000, maxPixels=1e13,
        )
        return ee.Feature(None, stats.set("date", image.date().format("YYYY-MM-dd")))

    return _fetch_with_retry(col, extract, year, "LST", _parse_lst)


def _parse_lst(feat: dict) -> dict:
    p = feat["properties"]
    return {
        "time": pd.Timestamp(p["date"], tz="UTC"),
        "lst_mean": p.get("LST_Day_1km_mean"),
        "lst_min": p.get("LST_Day_1km_min"),
        "lst_max": p.get("LST_Day_1km_max"),
    }


# ---------------------------------------------------------------------------
# SMAP Soil Moisture  (SPL4SMGP, daily, 11km) — available from 2015-03
# ---------------------------------------------------------------------------

SMAP_START_YEAR = 2015

def fetch_smap_year(bbox: list[float], year: int) -> list[dict]:
    if year < SMAP_START_YEAR:
        return []
    roi = ee.Geometry.Rectangle(bbox)
    # Use monthly composites to avoid too-many-aggregations on daily data
    rows: list[dict] = []
    for month in range(1, 13):
        m_start = f"{year}-{month:02d}-01"
        if month == 12:
            m_end = f"{year + 1}-01-01"
        else:
            m_end = f"{year}-{month + 1:02d}-01"

        col = (
            ee.ImageCollection("NASA/SMAP/SPL4SMGP/007")
            .filterDate(m_start, m_end)
            .filterBounds(roi)
            .select(["sm_surface"])
        )

        try:
            composite = col.mean()
            stats = composite.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=roi, scale=11000, maxPixels=1e13,
            )
            result = stats.getInfo()
            sm = result.get("sm_surface")
            if sm is not None:
                rows.append({
                    "time": pd.Timestamp(m_start, tz="UTC"),
                    "soil_moisture": sm,
                })
        except Exception:
            pass  # skip months with no data

    return rows


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------

def _fetch_with_retry(
    collection: ee.ImageCollection,
    extract_fn,
    year: int,
    label: str,
    parse_fn,
    max_attempts: int = 5,
) -> list[dict]:
    for attempt in range(max_attempts):
        try:
            result = collection.map(extract_fn).getInfo()
            return [parse_fn(f) for f in result["features"]]
        except Exception as e:
            wait = 15 * (attempt + 1)
            print(f"    {label} {year}: retry {attempt + 1}/{max_attempts} "
                  f"in {wait}s ({e})", flush=True)
            time.sleep(wait)
    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    init_gee()

    async with async_session() as session:
        # Clear old GEE data to avoid duplicates
        await session.execute(
            text("DELETE FROM eco_indicators WHERE source = 'MODIS_GEE'")
        )
        await session.commit()
        print("Cleared old MODIS_GEE data\n", flush=True)

        for region_id, info in REGIONS.items():
            name = info["name"]
            bbox = info["bbox"]
            print(f"{'=' * 60}", flush=True)
            print(f"  [{name}] (region_id={region_id})", flush=True)
            print(f"{'=' * 60}\n", flush=True)

            total_ndvi = 0
            total_evi = 0
            total_lst = 0
            total_smap = 0

            for year in range(START_YEAR, END_YEAR + 1):
                print(f"  --- {year} ---", flush=True)

                # NDVI / EVI
                ndvi_rows = fetch_ndvi_year(bbox, year)
                if ndvi_rows:
                    df = pd.DataFrame(ndvi_rows)
                    # NDVI
                    ndvi_df = df[["time", "ndvi_mean", "ndvi_min", "ndvi_max"]].dropna(subset=["ndvi_mean"])
                    for _, row in ndvi_df.iterrows():
                        await session.execute(
                            text("""INSERT INTO eco_indicators (time, region_id, indicator, value, source, resolution)
                                    VALUES (:t, :rid, 'ndvi', :v, 'MODIS_GEE', '500m')
                                    ON CONFLICT DO NOTHING"""),
                            {"t": row["time"], "rid": region_id, "v": float(row["ndvi_mean"])},
                        )
                    total_ndvi += len(ndvi_df)

                    # EVI
                    evi_df = df[["time", "evi_mean"]].dropna(subset=["evi_mean"])
                    for _, row in evi_df.iterrows():
                        await session.execute(
                            text("""INSERT INTO eco_indicators (time, region_id, indicator, value, source, resolution)
                                    VALUES (:t, :rid, 'evi', :v, 'MODIS_GEE', '500m')
                                    ON CONFLICT DO NOTHING"""),
                            {"t": row["time"], "rid": region_id, "v": float(row["evi_mean"])},
                        )
                    total_evi += len(evi_df)
                    print(f"    NDVI: {len(ndvi_df)} | EVI: {len(evi_df)}", flush=True)
                else:
                    print(f"    NDVI/EVI: FAILED", flush=True)

                await session.commit()
                time.sleep(3)

                # LST
                lst_rows = fetch_lst_year(bbox, year)
                if lst_rows:
                    for r in lst_rows:
                        if r["lst_mean"] is not None:
                            await session.execute(
                                text("""INSERT INTO eco_indicators (time, region_id, indicator, value, source, resolution)
                                        VALUES (:t, :rid, 'lst', :v, 'MODIS_GEE', '1km')
                                        ON CONFLICT DO NOTHING"""),
                                {"t": r["time"], "rid": region_id, "v": float(r["lst_mean"])},
                            )
                    total_lst += len([r for r in lst_rows if r["lst_mean"] is not None])
                    print(f"    LST:  {len(lst_rows)}", flush=True)
                else:
                    print(f"    LST:  FAILED", flush=True)

                await session.commit()
                time.sleep(3)

                # SMAP (from 2015)
                if year >= SMAP_START_YEAR:
                    smap_rows = fetch_smap_year(bbox, year)
                    if smap_rows:
                        for r in smap_rows:
                            await session.execute(
                                text("""INSERT INTO eco_indicators (time, region_id, indicator, value, source, resolution)
                                        VALUES (:t, :rid, 'soil_moisture', :v, 'SMAP_GEE', '11km')
                                        ON CONFLICT DO NOTHING"""),
                                {"t": r["time"], "rid": region_id, "v": float(r["soil_moisture"])},
                            )
                        total_smap += len(smap_rows)
                        print(f"    SMAP: {len(smap_rows)}", flush=True)
                    else:
                        print(f"    SMAP: no data", flush=True)

                    await session.commit()
                    time.sleep(2)

            print(f"\n  [{name}] Totals: NDVI={total_ndvi} EVI={total_evi} "
                  f"LST={total_lst} SMAP={total_smap}\n", flush=True)

        # Final verification
        print("=" * 60, flush=True)
        print("  VERIFICATION", flush=True)
        print("=" * 60, flush=True)
        result = await session.execute(text("""
            SELECT r.name, e.indicator, e.source, count(*),
                   min(e.time)::date, max(e.time)::date
            FROM eco_indicators e JOIN regions r ON r.id = e.region_id
            GROUP BY r.name, e.indicator, e.source
            ORDER BY r.name, e.indicator
        """))
        for row in result.fetchall():
            print(f"  {row[0]:15s} {row[1]:15s} {row[2]:12s} "
                  f"{row[3]:5d} records  ({row[4]} ~ {row[5]})", flush=True)

    print("\n=== DONE ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

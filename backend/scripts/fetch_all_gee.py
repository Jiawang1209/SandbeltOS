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
    """Serial per-image NDVI+EVI fetch (one reduceRegion per image)."""
    roi = ee.Geometry.Rectangle(bbox)
    col = (
        ee.ImageCollection("MODIS/061/MOD13A1")
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .filterBounds(roi)
        .select(["NDVI", "EVI"])
    )

    try:
        dates = col.aggregate_array("system:time_start").getInfo()
    except Exception as e:
        print(f"    NDVI {year}: list FAILED ({e})", flush=True)
        return []

    rows: list[dict] = []
    suffix_reducer = (
        ee.Reducer.mean()
        .combine(ee.Reducer.min(), sharedInputs=True)
        .combine(ee.Reducer.max(), sharedInputs=True)
    )
    for ts_ms in dates:
        date_str = pd.Timestamp(ts_ms, unit="ms", tz="UTC").strftime("%Y-%m-%d")
        for attempt in range(4):
            try:
                img = col.filter(ee.Filter.eq("system:time_start", ts_ms)).first()
                ndvi = img.select("NDVI").multiply(0.0001)
                evi = img.select("EVI").multiply(0.0001)
                ns = ndvi.reduceRegion(
                    reducer=suffix_reducer, geometry=roi, scale=500, maxPixels=1e13
                )
                es = evi.reduceRegion(
                    reducer=suffix_reducer, geometry=roi, scale=500, maxPixels=1e13
                )
                props = ns.combine(es).getInfo()
                rows.append({
                    "time": pd.Timestamp(date_str, tz="UTC"),
                    "ndvi_mean": props.get("NDVI_mean"),
                    "ndvi_min": props.get("NDVI_min"),
                    "ndvi_max": props.get("NDVI_max"),
                    "evi_mean": props.get("EVI_mean"),
                })
                break
            except Exception as e:
                wait = 5 * (attempt + 1)
                print(f"    NDVI {date_str}: {str(e)[:60]} — retry in {wait}s", flush=True)
                time.sleep(wait)
        time.sleep(0.4)
    return rows


# ---------------------------------------------------------------------------
# MODIS LST  (MOD11A2, 8-day, 1km)
# ---------------------------------------------------------------------------

def fetch_lst_year(bbox: list[float], year: int) -> list[dict]:
    """Serial per-image LST fetch."""
    roi = ee.Geometry.Rectangle(bbox)
    col = (
        ee.ImageCollection("MODIS/061/MOD11A2")
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .filterBounds(roi)
        .select(["LST_Day_1km"])
    )

    try:
        dates = col.aggregate_array("system:time_start").getInfo()
    except Exception as e:
        print(f"    LST {year}: list FAILED ({e})", flush=True)
        return []

    rows: list[dict] = []
    suffix_reducer = (
        ee.Reducer.mean()
        .combine(ee.Reducer.min(), sharedInputs=True)
        .combine(ee.Reducer.max(), sharedInputs=True)
    )
    for ts_ms in dates:
        date_str = pd.Timestamp(ts_ms, unit="ms", tz="UTC").strftime("%Y-%m-%d")
        for attempt in range(4):
            try:
                img = col.filter(ee.Filter.eq("system:time_start", ts_ms)).first()
                lst_c = img.select("LST_Day_1km").multiply(0.02).subtract(273.15)
                stats = lst_c.reduceRegion(
                    reducer=suffix_reducer, geometry=roi, scale=1000, maxPixels=1e13
                ).getInfo()
                rows.append({
                    "time": pd.Timestamp(date_str, tz="UTC"),
                    "lst_mean": stats.get("LST_Day_1km_mean"),
                    "lst_min": stats.get("LST_Day_1km_min"),
                    "lst_max": stats.get("LST_Day_1km_max"),
                })
                break
            except Exception as e:
                wait = 5 * (attempt + 1)
                print(f"    LST {date_str}: {str(e)[:60]} — retry in {wait}s", flush=True)
                time.sleep(wait)
        time.sleep(0.4)
    return rows


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

"""
Fetch ERA5 reanalysis weather data (2000-2025) for all regions.
Downloads monthly chunks, computes daily aggregates, writes to weather_data table.

New CDS API returns zip files with separate nc files for instant vs accumulated vars.

Usage:
    cd backend
    conda run -n sandbelt python -m scripts.fetch_era5
"""

import asyncio
import os
import tempfile
import time
import zipfile

import numpy as np
import pandas as pd
import xarray as xr
from sqlalchemy import text

from app.database import async_session

# ERA5 variables split by step type
INSTANT_VARS = [
    "2m_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
]
ACCUM_VARS = [
    "total_precipitation",
    "potential_evaporation",
]
ALL_VARS = INSTANT_VARS + ACCUM_VARS

REGIONS = {
    1: {"name": "科尔沁沙地", "bbox": [45, 119, 42, 124]},      # [N, W, S, E]
    2: {"name": "浑善达克沙地", "bbox": [43.5, 112, 42, 116.5]},
}

START_YEAR = 2000
END_YEAR = 2025  # ERA5 typically ~2-3 months behind


def fetch_era5_month(year: int, month: int, bbox: list[float]) -> pd.DataFrame | None:
    """Download one month of ERA5 data, return daily-aggregated DataFrame."""
    import cdsapi

    c = cdsapi.Client(quiet=True)
    out_path = os.path.join(tempfile.gettempdir(), f"era5_{year}_{month:02d}.zip")

    try:
        c.retrieve(
            "reanalysis-era5-single-levels",
            {
                "product_type": ["reanalysis"],
                "variable": ALL_VARS,
                "year": [str(year)],
                "month": [f"{month:02d}"],
                "day": [f"{d:02d}" for d in range(1, 32)],
                "time": ["00:00", "06:00", "12:00", "18:00"],
                "area": bbox,
                "data_format": "netcdf",
            },
            out_path,
        )
    except Exception as e:
        print(f"      download error: {e}", flush=True)
        return None

    # Extract zip
    tmpdir = tempfile.mkdtemp()
    try:
        datasets = []
        if zipfile.is_zipfile(out_path):
            with zipfile.ZipFile(out_path) as z:
                z.extractall(tmpdir)
                for name in z.namelist():
                    if name.endswith(".nc"):
                        ds = xr.open_dataset(os.path.join(tmpdir, name))
                        datasets.append(ds)
        else:
            datasets.append(xr.open_dataset(out_path))

        # Merge all variables into one dataset
        merged = xr.merge(datasets)

        # Spatial mean across all grid points
        spatial_mean = merged.mean(dim=["latitude", "longitude"])
        df = spatial_mean.to_dataframe().reset_index()

        for ds in datasets:
            ds.close()

    except Exception as e:
        print(f"      parse error: {e}", flush=True)
        return None
    finally:
        # Cleanup
        try:
            os.unlink(out_path)
        except OSError:
            pass

    if df.empty:
        return None

    # Compute derived fields
    if "u10" in df.columns and "v10" in df.columns:
        df["wind_speed"] = np.sqrt(df["u10"] ** 2 + df["v10"] ** 2)
        df["wind_direction"] = (180 + (180 / np.pi) * np.arctan2(df["u10"], df["v10"])) % 360
    else:
        df["wind_speed"] = np.nan
        df["wind_direction"] = np.nan

    # Daily aggregation
    time_col = "valid_time" if "valid_time" in df.columns else "time"
    daily = (
        df.groupby(df[time_col].dt.date)
        .agg(
            precipitation=("tp", lambda x: x.sum() * 1000 if "tp" in df.columns else 0),  # m -> mm
            temperature=("t2m", lambda x: x.mean() - 273.15 if "t2m" in df.columns else np.nan),  # K -> C
            wind_speed=("wind_speed", "mean"),
            wind_direction=("wind_direction", "mean"),
            evapotranspiration=("pev", lambda x: abs(x.mean()) * 1000 if "pev" in df.columns else np.nan),  # m -> mm
        )
        .reset_index()
    )
    daily.rename(columns={time_col: "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], utc=True)

    return daily


async def main() -> None:
    print("=== Fetching ERA5 Weather Data ===\n", flush=True)

    async with async_session() as session:
        # Clear old synthetic weather data
        await session.execute(
            text("DELETE FROM weather_data WHERE 1=1")
        )
        await session.commit()
        print("Cleared old weather data\n", flush=True)

        for region_id, info in REGIONS.items():
            name = info["name"]
            bbox = info["bbox"]
            print(f"{'=' * 50}", flush=True)
            print(f"  [{name}] (region_id={region_id})", flush=True)
            print(f"{'=' * 50}\n", flush=True)

            total_days = 0

            for year in range(START_YEAR, END_YEAR + 1):
                for month in range(1, 13):
                    print(f"  {year}-{month:02d}...", end=" ", flush=True)

                    for attempt in range(3):
                        daily = fetch_era5_month(year, month, bbox)
                        if daily is not None:
                            break
                        wait = 30 * (attempt + 1)
                        print(f"retry in {wait}s...", end=" ", flush=True)
                        time.sleep(wait)

                    if daily is None or daily.empty:
                        print("FAILED", flush=True)
                        continue

                    # Write to DB
                    for _, row in daily.iterrows():
                        await session.execute(
                            text("""
                                INSERT INTO weather_data
                                    (time, region_id, precipitation, temperature,
                                     wind_speed, wind_direction, evapotranspiration)
                                VALUES (:t, :rid, :precip, :temp, :ws, :wd, :et)
                                ON CONFLICT DO NOTHING
                            """),
                            {
                                "t": row["date"],
                                "rid": region_id,
                                "precip": _safe(row["precipitation"]),
                                "temp": _safe(row["temperature"]),
                                "ws": _safe(row["wind_speed"]),
                                "wd": _safe(row["wind_direction"]),
                                "et": _safe(row["evapotranspiration"]),
                            },
                        )

                    await session.commit()
                    total_days += len(daily)
                    print(f"{len(daily)} days", flush=True)

                    time.sleep(1)  # brief pause between months

            print(f"\n  [{name}] Total: {total_days} daily records\n", flush=True)

        # Verify
        print("=" * 50, flush=True)
        print("  VERIFICATION", flush=True)
        print("=" * 50, flush=True)
        result = await session.execute(text("""
            SELECT r.name, count(*), min(w.time)::date, max(w.time)::date
            FROM weather_data w JOIN regions r ON r.id = w.region_id
            GROUP BY r.name ORDER BY r.name
        """))
        for row in result.fetchall():
            print(f"  {row[0]:15s} {row[1]:5d} records  ({row[2]} ~ {row[3]})", flush=True)

    print("\n=== DONE ===", flush=True)


def _safe(val) -> float | None:
    if val is None or pd.isna(val):
        return None
    return round(float(val), 4)


if __name__ == "__main__":
    asyncio.run(main())

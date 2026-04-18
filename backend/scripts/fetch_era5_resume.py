"""
Resume ERA5 fetch for incomplete regions.
Queries DB for last successful month per region, resumes from next month.

Usage:
    cd backend
    conda run -n sandbelt python -m scripts.fetch_era5_resume
"""

import asyncio
import time

import pandas as pd
from sqlalchemy import text

from app.database import async_session
from scripts.fetch_era5 import REGIONS, END_YEAR, fetch_era5_month, _safe


async def last_month(session, region_id: int) -> tuple[int, int] | None:
    r = await session.execute(
        text("SELECT max(time) FROM weather_data WHERE region_id = :rid"),
        {"rid": region_id},
    )
    ts = r.scalar()
    if ts is None:
        return None
    return ts.year, ts.month


def next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


async def main() -> None:
    print("=== Resuming ERA5 Weather Data ===\n", flush=True)

    async with async_session() as session:
        for region_id, info in REGIONS.items():
            name = info["name"]
            bbox = info["bbox"]

            last = await last_month(session, region_id)
            if last is None:
                start_y, start_m = 2000, 1
            else:
                start_y, start_m = next_month(*last)

            if (start_y, start_m) > (END_YEAR, 12):
                print(f"[{name}] complete (last = {last}), skipping\n", flush=True)
                continue

            print(f"{'=' * 50}", flush=True)
            print(f"  [{name}] resume from {start_y}-{start_m:02d}", flush=True)
            print(f"{'=' * 50}\n", flush=True)

            total_days = 0
            y, m = start_y, start_m
            while (y, m) <= (END_YEAR, 12):
                print(f"  {y}-{m:02d}...", end=" ", flush=True)

                daily = None
                for attempt in range(3):
                    daily = fetch_era5_month(y, m, bbox)
                    if daily is not None:
                        break
                    wait = 30 * (attempt + 1)
                    print(f"retry {wait}s...", end=" ", flush=True)
                    time.sleep(wait)

                if daily is None or daily.empty:
                    print("FAILED", flush=True)
                    y, m = next_month(y, m)
                    continue

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

                time.sleep(1)
                y, m = next_month(y, m)

            print(f"\n  [{name}] +{total_days} days\n", flush=True)

        print("=" * 50, flush=True)
        print("  VERIFICATION", flush=True)
        print("=" * 50, flush=True)
        result = await session.execute(text("""
            SELECT r.name, count(*), min(w.time)::date, max(w.time)::date
            FROM weather_data w JOIN regions r ON r.id = w.region_id
            GROUP BY r.name ORDER BY r.name
        """))
        for row in result.fetchall():
            print(f"  {row[0]:15s} {row[1]:5d}  ({row[2]} ~ {row[3]})", flush=True)

    print("\n=== DONE ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

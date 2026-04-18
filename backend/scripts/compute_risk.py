"""
Batch compute ecological indicators and desertification risk from existing data.

For each region × month window present in the database, pulls NDVI / LST / SMAP
from eco_indicators plus wind speed from weather_data, then calls the pure
calculation functions in app.services.indicators and writes results to:

- desertification_risk: one row per region × month
- alerts: one row per region × month where risk_level >= 3, if not already alerted

Usage:
    cd backend
    conda run -n sandbelt python -m scripts.compute_risk
"""

import asyncio
import json
from collections import defaultdict

import pandas as pd
from sqlalchemy import text

from app.database import async_session
from app.services.indicators import (
    RISK_LEVEL_LABELS,
    assess_risk,
    calculate_carbon_density,
    calculate_fvc,
    calculate_sand_fixation,
    calculate_wind_erosion,
)


async def load_monthly_series(session, region_id: int) -> pd.DataFrame:
    """Aggregate eco_indicators + weather_data to monthly per region."""
    eco = await session.execute(
        text("""
            SELECT date_trunc('month', time) AS m,
                   indicator,
                   avg(value) AS value
            FROM eco_indicators
            WHERE region_id = :rid
            GROUP BY m, indicator
        """),
        {"rid": region_id},
    )
    eco_rows = eco.fetchall()
    eco_df = pd.DataFrame(eco_rows, columns=["month", "indicator", "value"])
    eco_pivot = (
        eco_df.pivot(index="month", columns="indicator", values="value")
        if not eco_df.empty
        else pd.DataFrame()
    )

    wx = await session.execute(
        text("""
            SELECT date_trunc('month', time) AS m,
                   avg(wind_speed) AS wind_speed,
                   avg(soil_moisture) AS sm_era5,
                   avg(precipitation) AS precip
            FROM weather_data
            WHERE region_id = :rid
            GROUP BY m
        """),
        {"rid": region_id},
    )
    wx_df = pd.DataFrame(
        wx.fetchall(), columns=["month", "wind_speed", "sm_era5", "precip"]
    ).set_index("month") if wx.rowcount != 0 else pd.DataFrame()

    # Outer join — keep months present in either source
    merged = eco_pivot.join(wx_df, how="outer") if not eco_pivot.empty else wx_df
    merged = merged.sort_index()
    return merged.reset_index()


def compute_row(row: pd.Series) -> dict | None:
    """Compute indicators for one monthly row. Returns None if NDVI missing."""
    ndvi = row.get("ndvi")
    if ndvi is None or pd.isna(ndvi):
        return None

    fvc = calculate_fvc(float(ndvi))
    carbon = calculate_carbon_density(float(ndvi))

    wind = row.get("wind_speed")
    wind = float(wind) if wind is not None and not pd.isna(wind) else 0.0

    # Prefer SMAP surface moisture; fall back to ERA5 soil_moisture if present
    sm_smap = row.get("soil_moisture")
    sm = sm_smap if sm_smap is not None and not pd.isna(sm_smap) else row.get("sm_era5")
    sm = float(sm) if sm is not None and not pd.isna(sm) else None

    lst = row.get("lst")
    lst = float(lst) if lst is not None and not pd.isna(lst) else None

    wem = calculate_wind_erosion(wind, fvc, sm)
    sand_fix = calculate_sand_fixation(wind, fvc, sm)
    risk = assess_risk(fvc, wem, sm, lst)

    return {
        "time": row["month"],
        "fvc": round(fvc, 4),
        "carbon_density": round(carbon, 2),
        "wind_erosion_modulus": round(wem, 2),
        "sand_fixation_amount": round(sand_fix, 2),
        "risk_score": risk.risk_score,
        "risk_level": risk.risk_level,
        "factors": {
            **risk.factors,
            "ndvi": round(float(ndvi), 4),
            "wind_speed": round(wind, 2),
            "soil_moisture": round(sm, 4) if sm is not None else None,
            "lst": round(lst, 2) if lst is not None else None,
        },
    }


async def main() -> None:
    print("=== Computing desertification risk ===\n", flush=True)

    async with async_session() as session:
        regions = await session.execute(
            text("SELECT id, name FROM regions WHERE level = 'subregion' ORDER BY id")
        )
        region_rows = regions.fetchall()

        # Reset tables
        await session.execute(text("DELETE FROM desertification_risk"))
        await session.execute(text("DELETE FROM alerts WHERE alert_type = 'desertification'"))
        await session.commit()
        print("Cleared existing risk + alerts\n", flush=True)

        total_risk_rows = 0
        total_alerts = 0

        for region_id, name in region_rows:
            print(f"--- {name} (region_id={region_id}) ---", flush=True)
            df = await load_monthly_series(session, region_id)
            if df.empty:
                print("  no data, skipping\n", flush=True)
                continue

            level_counts: dict[int, int] = defaultdict(int)
            region_rows_written = 0

            for _, row in df.iterrows():
                r = compute_row(row)
                if r is None:
                    continue

                await session.execute(
                    text("""
                        INSERT INTO desertification_risk
                            (time, region_id, risk_level, risk_score,
                             wind_erosion_modulus, sand_fixation_amount, factors)
                        VALUES
                            (:t, :rid, :lvl, :score, :wem, :sf, CAST(:factors AS jsonb))
                    """),
                    {
                        "t": r["time"],
                        "rid": region_id,
                        "lvl": r["risk_level"],
                        "score": r["risk_score"],
                        "wem": r["wind_erosion_modulus"],
                        "sf": r["sand_fixation_amount"],
                        "factors": json.dumps({
                            **r["factors"],
                            "fvc": r["fvc"],
                            "carbon_density": r["carbon_density"],
                        }),
                    },
                )
                level_counts[r["risk_level"]] += 1
                region_rows_written += 1

                if r["risk_level"] >= 3:
                    label = RISK_LEVEL_LABELS[r["risk_level"]]
                    severity = "high" if r["risk_level"] == 3 else "critical"
                    msg = (
                        f"{name} {r['time']:%Y-%m}: {label}"
                        f" (score={r['risk_score']:.2f}, FVC={r['fvc']:.2f},"
                        f" WEM={r['wind_erosion_modulus']:.0f} t/km²·月)"
                    )
                    await session.execute(
                        text("""
                            INSERT INTO alerts
                                (created_at, region_id, alert_type, severity, message)
                            VALUES (:t, :rid, 'desertification', :sev, :msg)
                        """),
                        {"t": r["time"], "rid": region_id, "sev": severity, "msg": msg},
                    )
                    total_alerts += 1

            await session.commit()
            total_risk_rows += region_rows_written

            summary = " ".join(
                f"L{lvl}={level_counts[lvl]}" for lvl in sorted(level_counts)
            )
            print(f"  {region_rows_written} months written  ({summary})\n", flush=True)

        # Final verification
        print("=" * 50, flush=True)
        print("  VERIFICATION", flush=True)
        print("=" * 50, flush=True)
        result = await session.execute(text("""
            SELECT r.name, d.risk_level, count(*)
            FROM desertification_risk d JOIN regions r ON r.id = d.region_id
            GROUP BY r.name, d.risk_level
            ORDER BY r.name, d.risk_level
        """))
        for row in result.fetchall():
            print(f"  {row[0]:15s} L{row[1]}  {row[2]:4d} months", flush=True)

        print(f"\n  Total risk rows: {total_risk_rows}", flush=True)
        print(f"  Total alerts:    {total_alerts}", flush=True)

    print("\n=== DONE ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

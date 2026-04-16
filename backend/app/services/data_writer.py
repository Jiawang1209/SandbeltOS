import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def write_eco_indicators(
    session: AsyncSession,
    df: pd.DataFrame,
    region_id: int,
    indicator: str,
    source: str = "MODIS",
    resolution: str = "500m",
) -> int:
    """
    Write ecological indicator data to eco_indicators table.

    Args:
        df: DataFrame with 'time' and value column (e.g. 'ndvi_mean')
        region_id: Target region ID
        indicator: Indicator name ('ndvi', 'evi', 'lst', etc.)
        source: Data source name
        resolution: Spatial resolution

    Returns:
        Number of rows inserted
    """
    value_col = _find_value_column(df, indicator)
    if value_col is None:
        raise ValueError(f"No suitable value column found for indicator '{indicator}' in {list(df.columns)}")

    rows_inserted = 0
    for _, row in df.iterrows():
        val = row[value_col]
        if pd.isna(val):
            continue

        await session.execute(
            text("""
                INSERT INTO eco_indicators (time, region_id, indicator, value, source, resolution)
                VALUES (:time, :region_id, :indicator, :value, :source, :resolution)
                ON CONFLICT DO NOTHING
            """),
            {
                "time": row["time"],
                "region_id": region_id,
                "indicator": indicator,
                "value": float(val),
                "source": source,
                "resolution": resolution,
            },
        )
        rows_inserted += 1

    await session.commit()
    return rows_inserted


async def write_weather_data(
    session: AsyncSession,
    df: pd.DataFrame,
    region_id: int,
) -> int:
    """
    Write weather data to weather_data table.

    Args:
        df: DataFrame with 'date' column and weather fields
        region_id: Target region ID

    Returns:
        Number of rows inserted
    """
    rows_inserted = 0
    for _, row in df.iterrows():
        time_val = row.get("date") or row.get("time")
        await session.execute(
            text("""
                INSERT INTO weather_data (time, region_id, precipitation, wind_speed,
                    wind_direction, temperature, evapotranspiration, soil_moisture)
                VALUES (:time, :region_id, :precipitation, :wind_speed,
                    :wind_direction, :temperature, :evapotranspiration, :soil_moisture)
                ON CONFLICT DO NOTHING
            """),
            {
                "time": time_val,
                "region_id": region_id,
                "precipitation": _safe_float(row.get("precipitation")),
                "wind_speed": _safe_float(row.get("wind_speed")),
                "wind_direction": _safe_float(row.get("wind_direction")),
                "temperature": _safe_float(row.get("temperature")),
                "evapotranspiration": _safe_float(row.get("evapotranspiration")),
                "soil_moisture": _safe_float(row.get("soil_moisture")),
            },
        )
        rows_inserted += 1

    await session.commit()
    return rows_inserted


def _find_value_column(df: pd.DataFrame, indicator: str) -> str | None:
    """Find the appropriate value column for a given indicator."""
    candidates = [
        f"{indicator}_mean",
        f"{indicator}",
        "value",
    ]
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _safe_float(val) -> float | None:
    """Convert to float, returning None for NaN/None."""
    if val is None or pd.isna(val):
        return None
    return float(val)

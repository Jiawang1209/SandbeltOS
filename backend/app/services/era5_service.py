from __future__ import annotations

import numpy as np
import os
import pandas as pd
import tempfile


ERA5_VARIABLES = [
    "total_precipitation",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_temperature",
    "potential_evaporation",
]

# Horqin Sandy Land approximate bounding box [North, West, South, East]
HORQIN_BBOX = [45.0, 119.0, 42.0, 124.0]


def fetch_era5_daily(
    year: int,
    month: int,
    bbox: list[float] | None = None,
) -> pd.DataFrame:
    """
    Download ERA5 reanalysis data for a given month and compute daily aggregates.

    Args:
        year: Target year
        month: Target month (1-12)
        bbox: [north, west, south, east] bounding box

    Returns:
        DataFrame with daily weather stats aggregated over the bounding box
    """
    import cdsapi
    import xarray as xr

    if bbox is None:
        bbox = HORQIN_BBOX

    c = cdsapi.Client()

    output_path = os.path.join(tempfile.gettempdir(), f"era5_{year}_{month:02d}.nc")

    c.retrieve(
        "reanalysis-era5-single-levels",
        {
            "product_type": "reanalysis",
            "variable": ERA5_VARIABLES,
            "year": str(year),
            "month": f"{month:02d}",
            "day": [f"{d:02d}" for d in range(1, 32)],
            "time": ["00:00", "06:00", "12:00", "18:00"],
            "area": bbox,
            "format": "netcdf",
        },
        output_path,
    )

    ds = xr.open_dataset(output_path)
    df = ds.to_dataframe().reset_index()
    ds.close()

    # Compute derived fields
    df["wind_speed"] = np.sqrt(df["u10"] ** 2 + df["v10"] ** 2)
    df["wind_direction"] = (
        180 + (180 / np.pi) * np.arctan2(df["u10"], df["v10"])
    ) % 360

    # Daily aggregation: spatial mean across all grid points, then temporal aggregation
    daily = (
        df.groupby(df["time"].dt.date)
        .agg(
            precipitation=("tp", "sum"),
            temperature=("t2m", lambda x: x.mean() - 273.15),  # K → C
            wind_speed=("wind_speed", "mean"),
            wind_direction=("wind_direction", "mean"),
            evapotranspiration=("pev", lambda x: abs(x.mean()) * 1000),  # m → mm
        )
        .reset_index()
    )
    daily.rename(columns={"time": "date"}, inplace=True)

    # Clean up temp file
    try:
        os.unlink(output_path)
    except OSError:
        pass

    return daily


def generate_synthetic_weather(
    start_date: str,
    end_date: str,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic weather data for development/testing when ERA5 is unavailable.
    Mimics semi-arid climate patterns of the Horqin Sandy Land region.

    Args:
        start_date: 'YYYY-MM-DD'
        end_date: 'YYYY-MM-DD'

    Returns:
        DataFrame with columns matching ERA5 output
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start_date, end_date, freq="D", tz="UTC")
    n = len(dates)

    # Day of year for seasonal patterns
    doy = dates.dayofyear.values
    seasonal = np.sin(2 * np.pi * (doy - 80) / 365)  # peak around late June

    # Temperature: -20C winter to +28C summer + noise
    temperature = 4 + 24 * seasonal + rng.normal(0, 3, n)

    # Precipitation: concentrated in summer (Jun-Sep), sparse in winter
    precip_base = np.maximum(0, 1.5 * seasonal + 0.5)
    precipitation = rng.exponential(precip_base) * rng.binomial(1, 0.3 + 0.2 * seasonal, n)

    # Wind speed: stronger in spring (Mar-May)
    spring_factor = np.exp(-((doy - 100) ** 2) / 2000)
    wind_speed = 3 + 4 * spring_factor + rng.normal(0, 1.5, n)
    wind_speed = np.maximum(0.5, wind_speed)

    # Wind direction: predominantly NW in winter, variable in summer
    wind_direction = 315 + 30 * seasonal + rng.normal(0, 40, n)
    wind_direction = wind_direction % 360

    # Evapotranspiration: follows temperature
    evapotranspiration = np.maximum(0, 1.5 + 3.5 * seasonal + rng.normal(0, 0.5, n))

    # Soil moisture: inverse of temperature, with rainfall influence
    soil_moisture = 0.08 + 0.04 * (-seasonal) + 0.002 * precipitation + rng.normal(0, 0.01, n)
    soil_moisture = np.clip(soil_moisture, 0.02, 0.25)

    return pd.DataFrame(
        {
            "date": dates,
            "precipitation": np.round(precipitation, 2),
            "temperature": np.round(temperature, 1),
            "wind_speed": np.round(wind_speed, 1),
            "wind_direction": np.round(wind_direction, 1),
            "evapotranspiration": np.round(evapotranspiration, 2),
            "soil_moisture": np.round(soil_moisture, 4),
        }
    )

"""Unit tests for synthetic data generators (pure functions, no DB)."""

import numpy as np
import pandas as pd
import pytest

from app.services.era5_service import generate_synthetic_weather


class TestSyntheticWeather:
    def test_returns_dataframe(self):
        df = generate_synthetic_weather("2023-01-01", "2023-01-31")
        assert isinstance(df, pd.DataFrame)

    def test_date_range(self):
        df = generate_synthetic_weather("2023-01-01", "2023-01-31")
        assert len(df) == 31

    def test_columns_present(self):
        df = generate_synthetic_weather("2023-01-01", "2023-01-10")
        expected = {
            "date",
            "precipitation",
            "temperature",
            "wind_speed",
            "wind_direction",
            "evapotranspiration",
            "soil_moisture",
        }
        assert expected == set(df.columns)

    def test_no_nan_values(self):
        df = generate_synthetic_weather("2020-01-01", "2024-12-31")
        assert not df.isnull().any().any()

    def test_precipitation_non_negative(self):
        df = generate_synthetic_weather("2020-01-01", "2024-12-31")
        assert (df["precipitation"] >= 0).all()

    def test_wind_speed_positive(self):
        df = generate_synthetic_weather("2020-01-01", "2024-12-31")
        assert (df["wind_speed"] > 0).all()

    def test_wind_direction_range(self):
        df = generate_synthetic_weather("2020-01-01", "2024-12-31")
        assert (df["wind_direction"] >= 0).all()
        assert (df["wind_direction"] < 360).all()

    def test_soil_moisture_range(self):
        df = generate_synthetic_weather("2020-01-01", "2024-12-31")
        assert (df["soil_moisture"] >= 0.02).all()
        assert (df["soil_moisture"] <= 0.25).all()

    def test_deterministic_with_seed(self):
        df1 = generate_synthetic_weather("2023-01-01", "2023-01-10", seed=99)
        df2 = generate_synthetic_weather("2023-01-01", "2023-01-10", seed=99)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seed_different_data(self):
        df1 = generate_synthetic_weather("2023-01-01", "2023-01-10", seed=1)
        df2 = generate_synthetic_weather("2023-01-01", "2023-01-10", seed=2)
        assert not df1["temperature"].equals(df2["temperature"])

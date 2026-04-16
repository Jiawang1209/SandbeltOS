"""Unit tests for data_writer helper functions."""

import pandas as pd
import pytest

from app.services.data_writer import _find_value_column, _safe_float


class TestFindValueColumn:
    def test_finds_indicator_mean_column(self):
        df = pd.DataFrame({"time": [1], "ndvi_mean": [0.3]})
        assert _find_value_column(df, "ndvi") == "ndvi_mean"

    def test_finds_exact_indicator_column(self):
        df = pd.DataFrame({"time": [1], "ndvi": [0.3]})
        assert _find_value_column(df, "ndvi") == "ndvi"

    def test_finds_value_column_as_fallback(self):
        df = pd.DataFrame({"time": [1], "value": [0.3]})
        assert _find_value_column(df, "ndvi") == "value"

    def test_prefers_mean_over_exact(self):
        df = pd.DataFrame({"time": [1], "ndvi_mean": [0.3], "ndvi": [0.2]})
        assert _find_value_column(df, "ndvi") == "ndvi_mean"

    def test_returns_none_when_not_found(self):
        df = pd.DataFrame({"time": [1], "other_col": [0.3]})
        assert _find_value_column(df, "ndvi") is None


class TestSafeFloat:
    def test_converts_int(self):
        assert _safe_float(42) == 42.0

    def test_converts_float(self):
        assert _safe_float(3.14) == 3.14

    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_nan_returns_none(self):
        assert _safe_float(float("nan")) is None

    def test_numpy_nan_returns_none(self):
        import numpy as np
        assert _safe_float(np.nan) is None

    def test_numpy_float(self):
        import numpy as np
        result = _safe_float(np.float64(2.5))
        assert result == 2.5
        assert isinstance(result, float)

"""Unit tests for the forecast cache warming script.

Mocks `scripts.warm_forecast_cache.warm_one` and `list_regions` so the
test runs without a DB or Prophet. Validates that warm_all iterates
correctly, tolerates partial failure, and respects --region filter.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from scripts import warm_forecast_cache as wfc


@pytest.mark.unit
class TestWarmAll:
    @pytest.mark.asyncio
    async def test_warms_every_region(self) -> None:
        with patch.object(wfc, "list_regions", new=AsyncMock(return_value=[(1, "A"), (2, "B")])), \
             patch.object(wfc, "warm_one", new=AsyncMock(side_effect=[
                wfc.WarmResult(1, "A", ok=True, elapsed_s=0.1, detail="fitted"),
                wfc.WarmResult(2, "B", ok=True, elapsed_s=0.1, detail="fitted"),
             ])) as warm_one_mock:
            results = await wfc.warm_all()
        assert warm_one_mock.await_count == 2
        assert [r.region_id for r in results] == [1, 2]
        assert all(r.ok for r in results)

    @pytest.mark.asyncio
    async def test_dry_run_skips_warm_one(self) -> None:
        with patch.object(wfc, "list_regions", new=AsyncMock(return_value=[(1, "A")])), \
             patch.object(wfc, "warm_one", new=AsyncMock()) as warm_one_mock:
            results = await wfc.warm_all(dry_run=True)
        warm_one_mock.assert_not_awaited()
        assert results[0].detail == "dry-run"
        assert results[0].ok

    @pytest.mark.asyncio
    async def test_region_filter_passed_through(self) -> None:
        with patch.object(wfc, "list_regions", new=AsyncMock(return_value=[(7, "X")])) as list_mock, \
             patch.object(wfc, "warm_one", new=AsyncMock(return_value=wfc.WarmResult(
                7, "X", ok=True, elapsed_s=0.0, detail="fitted",
             ))):
            await wfc.warm_all(region=7)
        list_mock.assert_awaited_once_with(only=7)

    @pytest.mark.asyncio
    async def test_partial_failure_returns_results(self) -> None:
        with patch.object(wfc, "list_regions", new=AsyncMock(return_value=[(1, "A"), (2, "B")])), \
             patch.object(wfc, "warm_one", new=AsyncMock(side_effect=[
                wfc.WarmResult(1, "A", ok=True, elapsed_s=0.0, detail="fitted"),
                wfc.WarmResult(2, "B", ok=False, elapsed_s=0.0, detail="skipped (no history)"),
             ])):
            results = await wfc.warm_all()
        assert [r.ok for r in results] == [True, False]

    @pytest.mark.asyncio
    async def test_no_regions_returns_empty(self) -> None:
        with patch.object(wfc, "list_regions", new=AsyncMock(return_value=[])), \
             patch.object(wfc, "warm_one", new=AsyncMock()) as warm_one_mock:
            results = await wfc.warm_all()
        assert results == []
        warm_one_mock.assert_not_awaited()


@pytest.mark.unit
class TestMain:
    def test_exit_zero_on_all_success(self) -> None:
        with patch.object(wfc, "warm_all", new=AsyncMock(return_value=[
            wfc.WarmResult(1, "A", ok=True, elapsed_s=0.0, detail="fitted"),
        ])):
            rc = wfc.main(["--region", "1"])
        assert rc == 0

    def test_exit_nonzero_on_total_failure(self) -> None:
        with patch.object(wfc, "warm_all", new=AsyncMock(return_value=[
            wfc.WarmResult(1, "A", ok=False, elapsed_s=0.0, detail="error: boom"),
        ])):
            rc = wfc.main([])
        assert rc == 1

    def test_exit_zero_on_empty_results(self) -> None:
        """No regions in DB ≠ failure — the script just no-ops."""
        with patch.object(wfc, "warm_all", new=AsyncMock(return_value=[])):
            rc = wfc.main([])
        assert rc == 0

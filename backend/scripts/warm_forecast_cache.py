"""Pre-warm the Prophet NDVI forecast cache.

The `/api/v1/prediction/ndvi-forecast` endpoint memoizes Prophet fits in
Redis keyed on (region, indicator, horizon, today). Cold-start cost is
several seconds per region — the first user of the day pays for it.

This script iterates every region in the DB, fits Prophet for the
default horizon (12 × 16D ≈ half a year) up-front, and writes the
result to Redis. Subsequent dashboard loads hit the cache.

Idempotent: a region already cached for today returns immediately
without re-fitting. Safe to run repeatedly (cron, Prefect, manual).

Usage:
    cd backend
    python -m scripts.warm_forecast_cache               # all regions
    python -m scripts.warm_forecast_cache --region 1    # one region
    python -m scripts.warm_forecast_cache --horizon 24  # custom horizon
    python -m scripts.warm_forecast_cache --dry-run     # list, don't fit
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from dataclasses import dataclass

from sqlalchemy import select

from app.database import async_session
from app.models.orm import Region
from app.services import prediction as pred_svc

logger = logging.getLogger("warm_forecast_cache")

DEFAULT_INDICATOR = "ndvi"
DEFAULT_HORIZON = 12


@dataclass
class WarmResult:
    region_id: int
    region_name: str
    ok: bool
    elapsed_s: float
    detail: str  # "fitted" / "skipped (no history)" / "error: ..."


async def warm_one(
    region_id: int,
    region_name: str,
    indicator: str,
    horizon: int,
) -> WarmResult:
    t0 = time.perf_counter()
    async with async_session() as session:
        try:
            await pred_svc.forecast_indicator(
                region_id=region_id,
                indicator=indicator,
                horizon_steps=horizon,
                db=session,
                use_cache=True,
            )
        except ValueError as exc:
            # Insufficient history is expected for newly-seeded regions
            # before fetch_all_gee runs — log + continue, don't abort.
            return WarmResult(
                region_id=region_id,
                region_name=region_name,
                ok=False,
                elapsed_s=time.perf_counter() - t0,
                detail=f"skipped ({exc})",
            )
        except Exception as exc:  # noqa: BLE001 — best-effort warm; never crash caller
            return WarmResult(
                region_id=region_id,
                region_name=region_name,
                ok=False,
                elapsed_s=time.perf_counter() - t0,
                detail=f"error: {exc}",
            )
    return WarmResult(
        region_id=region_id,
        region_name=region_name,
        ok=True,
        elapsed_s=time.perf_counter() - t0,
        detail="fitted",
    )


async def list_regions(only: int | None) -> list[tuple[int, str]]:
    async with async_session() as session:
        stmt = select(Region.id, Region.name).order_by(Region.id)
        if only is not None:
            stmt = stmt.where(Region.id == only)
        rows = (await session.execute(stmt)).all()
    return [(r[0], r[1]) for r in rows]


async def warm_all(
    indicator: str = DEFAULT_INDICATOR,
    horizon: int = DEFAULT_HORIZON,
    region: int | None = None,
    dry_run: bool = False,
) -> list[WarmResult]:
    """Warm the forecast cache for every region (or a single one).

    Serial by design: Prophet's `model.fit()` is CPU-bound and releases
    the GIL only inside cmdstanpy's C code, so asyncio.gather wouldn't
    actually parallelize the fits and would just contend on the same
    SQLAlchemy connection pool. Two regions × ~5s each is fine sequential.
    """
    regions = await list_regions(only=region)
    if not regions:
        logger.warning("no regions matched filter region=%s", region)
        return []

    logger.info(
        "warming %d region(s) × indicator=%s × horizon=%d (dry_run=%s)",
        len(regions),
        indicator,
        horizon,
        dry_run,
    )

    results: list[WarmResult] = []
    for rid, name in regions:
        if dry_run:
            logger.info("  would warm: region %d (%s)", rid, name)
            results.append(WarmResult(rid, name, ok=True, elapsed_s=0.0, detail="dry-run"))
            continue
        r = await warm_one(rid, name, indicator, horizon)
        marker = "ok" if r.ok else "skip"
        logger.info("  [%s] region %d (%s): %s (%.2fs)", marker, rid, name, r.detail, r.elapsed_s)
        results.append(r)

    n_ok = sum(1 for r in results if r.ok and r.detail != "dry-run")
    n_skip = sum(1 for r in results if not r.ok)
    total_s = sum(r.elapsed_s for r in results)
    logger.info("done: %d warmed, %d skipped, %.2fs total", n_ok, n_skip, total_s)
    return results


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Pre-warm Prophet NDVI forecast cache for all regions."
    )
    p.add_argument("--region", type=int, default=None, help="Warm only this region ID")
    p.add_argument(
        "--indicator", default=DEFAULT_INDICATOR, help=f"Indicator (default: {DEFAULT_INDICATOR})"
    )
    p.add_argument(
        "--horizon",
        type=int,
        default=DEFAULT_HORIZON,
        help=f"Forecast horizon steps (default: {DEFAULT_HORIZON})",
    )
    p.add_argument("--dry-run", action="store_true", help="List regions only, don't fit")
    p.add_argument("--verbose", "-v", action="store_true", help="DEBUG logging")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    results = asyncio.run(
        warm_all(
            indicator=args.indicator,
            horizon=args.horizon,
            region=args.region,
            dry_run=args.dry_run,
        )
    )
    # Exit non-zero only if everything failed — partial success is still
    # a win (one warm region > zero warm regions).
    if results and not any(r.ok for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

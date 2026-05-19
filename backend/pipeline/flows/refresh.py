"""Prefect flows for scheduled remote-sensing + risk refresh.

Two flows wrap the existing `scripts.fetch_*` + `scripts.compute_risk`
entry points so they can be:
  * scheduled by Prefect (16-day GEE cadence, daily ERA5 cadence), or
  * run ad-hoc via this module's CLI.

Each task delegates to the script's `async def main()` so the upstream
behaviour (chunking, DELETE-before-INSERT for `eco_indicators`,
serial-per-image GEE pacing) stays the single source of truth — this
file is just orchestration.

Schedules (cron):
  * `gee_refresh_flow`:  every 16 days at 02:00 UTC
  * `era5_refresh_flow`: daily         at 03:00 UTC
After each fetch the risk timeseries is recomputed so dashboards always
reflect the freshest indicators.

Usage
-----
Ad-hoc (no scheduler):
    python -m pipeline.flows.refresh --run gee
    python -m pipeline.flows.refresh --run era5

Start the long-running scheduler (foreground loop):
    python -m pipeline.flows.refresh --serve

The scheduler uses Prefect's local `serve()` runtime — no work pool or
agent needed. Move to `prefect deploy` + a worker when we outgrow it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make this script importable as `python -m pipeline.flows.refresh` from backend/.
# Heavy imports (prefect, the scripts themselves) are deferred so --help
# works without the full backend env installed.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


# ---------------------------------------------------------------------
# Tasks — one per script. Each delegates to the script's existing
# `async def main()` so the upstream pacing / retry / DELETE-first
# logic stays canonical.
# ---------------------------------------------------------------------


def _build_flows():
    """Construct Prefect flow + task objects.

    Wrapped in a function so the prefect import is lazy — running the
    CLI with `--help` doesn't require prefect to be installed.
    """
    from prefect import flow, task  # noqa: PLC0415

    @task(
        name="fetch-gee-all",
        retries=2,
        retry_delay_seconds=300,
        timeout_seconds=4 * 3600,  # GEE pull can take 30-60 min
    )
    async def fetch_gee_all_task() -> None:
        from scripts.fetch_all_gee import main as _main  # noqa: PLC0415

        await _main()

    @task(
        name="fetch-era5",
        retries=2,
        retry_delay_seconds=300,
        timeout_seconds=6 * 3600,  # CDS queue can be slow
    )
    async def fetch_era5_task() -> None:
        # `fetch_era5_resume` is the resumable variant — safer for
        # large files and intermittent CDS queue stalls.
        from scripts.fetch_era5_resume import main as _main  # noqa: PLC0415

        await _main()

    @task(
        name="compute-risk",
        retries=1,
        retry_delay_seconds=60,
        timeout_seconds=30 * 60,
    )
    async def compute_risk_task() -> None:
        from scripts.compute_risk import main as _main  # noqa: PLC0415

        await _main()

    @flow(name="gee-refresh", log_prints=True)
    async def gee_refresh_flow() -> None:
        """16-day cadence: pull MODIS NDVI/EVI/LST + SMAP, recompute risk."""
        await fetch_gee_all_task()
        await compute_risk_task()

    @flow(name="era5-refresh", log_prints=True)
    async def era5_refresh_flow() -> None:
        """Daily cadence: pull ERA5 weather, recompute risk."""
        await fetch_era5_task()
        await compute_risk_task()

    return gee_refresh_flow, era5_refresh_flow


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        choices=["gee", "era5"],
        help="Run one flow ad-hoc and exit.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help=(
            "Register both flows with Prefect's local scheduler and "
            "loop forever (Ctrl-C to stop). GEE every 16 days at "
            "02:00 UTC; ERA5 every day at 03:00 UTC."
        ),
    )
    args = parser.parse_args()

    if not args.run and not args.serve:
        parser.error("pass --run {gee,era5} or --serve")

    gee_refresh_flow, era5_refresh_flow = _build_flows()

    if args.run:
        import asyncio  # noqa: PLC0415

        flow = gee_refresh_flow if args.run == "gee" else era5_refresh_flow
        asyncio.run(flow())
        return 0

    # --serve path: register both flows and block.
    from prefect import serve  # noqa: PLC0415

    gee_deploy = gee_refresh_flow.to_deployment(
        name="gee-refresh-16d",
        cron="0 2 */16 * *",  # every 16th day at 02:00 UTC
    )
    era5_deploy = era5_refresh_flow.to_deployment(
        name="era5-refresh-daily",
        cron="0 3 * * *",  # every day at 03:00 UTC
    )
    print(
        "Starting Prefect serve loop — Ctrl-C to stop.\n"
        "  gee-refresh-16d:   cron '0 2 */16 * *'\n"
        "  era5-refresh-daily: cron '0 3 * * *'\n",
        flush=True,
    )
    serve(gee_deploy, era5_deploy)
    return 0


if __name__ == "__main__":
    sys.exit(main())

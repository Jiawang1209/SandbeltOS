"""Fetch MCD12Q1 IGBP land-cover annual composition per sandy land.

For each subregion polygon (bbox_json) and each year 2001-2023, we ask GEE for
the pixel histogram of LC_Type1 (IGBP) inside the polygon at 500m. The raw
17-class IGBP taxonomy is then collapsed into five buckets that tell the sandy
land story:

- barren   — IGBP 16 (Barren or sparsely vegetated)
- grass    — IGBP 10 (Grasslands)
- shrub    — IGBP 6, 7, 8, 9 (Closed/Open Shrublands, Savannas, Woody Savannas)
- forest   — IGBP 1–5 (all Forest classes)
- crop     — IGBP 12, 14 (Croplands + Cropland/Natural mosaic)
- other    — everything else (wetlands, urban, snow, water)

Output is written to backend/data/landcover/{region_id}.json so the FastAPI
endpoint can serve it without re-querying GEE on every request.

Usage:
    cd backend
    https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 \\
    conda run -n sandbelt python -m scripts.fetch_landcover
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import ee
from sqlalchemy import text

from app.database import async_session

logger = logging.getLogger(__name__)

GEE_PROJECT = "ee-yueliu19921209"
START_YEAR = 2001
END_YEAR = 2023  # MCD12Q1 has a ~1-year lag; 2024 may not be published yet.

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "landcover"

# IGBP class → frontend bucket. Keys are int class codes.
IGBP_TO_BUCKET: dict[int, str] = {
    1: "forest", 2: "forest", 3: "forest", 4: "forest", 5: "forest",
    6: "shrub", 7: "shrub", 8: "shrub", 9: "shrub",
    10: "grass",
    11: "other", 13: "other", 15: "other", 17: "other",
    12: "crop", 14: "crop",
    16: "barren",
}
BUCKETS = ["barren", "grass", "shrub", "crop", "forest", "other"]


def fetch_year(geometry: ee.Geometry, year: int) -> dict[str, float] | None:
    """Return bucket → pixel share (0..1) for one year, or None on failure."""
    img = (
        ee.ImageCollection("MODIS/061/MCD12Q1")
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .select("LC_Type1")
        .first()
    )

    hist = img.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=geometry,
        scale=500,
        maxPixels=1e13,
    )

    for attempt in range(5):
        try:
            raw = hist.getInfo()
            break
        except Exception as exc:  # noqa: BLE001
            wait = 15 * (attempt + 1)
            logger.warning("retry %s/5 in %ss (%s)", attempt + 1, wait, exc)
            time.sleep(wait)
    else:
        return None

    counts: dict = raw.get("LC_Type1") or {}
    if not counts:
        return None

    totals = {b: 0.0 for b in BUCKETS}
    total_all = 0.0
    for cls_str, px in counts.items():
        bucket = IGBP_TO_BUCKET.get(int(cls_str), "other")
        totals[bucket] += float(px)
        total_all += float(px)

    if total_all <= 0:
        return None

    return {b: totals[b] / total_all for b in BUCKETS}


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ee.Initialize(project=GEE_PROJECT)
    logger.info("GEE initialized")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, name, bbox_json FROM regions "
                    "WHERE level = 'subregion' ORDER BY id"
                )
            )
        ).fetchall()

    for row in rows:
        region_id, name, bbox_raw = row[0], row[1], row[2]
        bbox = json.loads(bbox_raw) if isinstance(bbox_raw, str) else bbox_raw
        if not bbox or "coordinates" not in bbox:
            logger.warning("[%s] no polygon, skipping", name)
            continue

        geometry = (
            ee.Geometry.MultiPolygon(bbox["coordinates"])
            if bbox.get("type") == "MultiPolygon"
            else ee.Geometry.Polygon(bbox["coordinates"])
        )

        out_path = OUT_DIR / f"{region_id}.json"
        cached = {}
        if out_path.exists():
            cached = json.loads(out_path.read_text())

        series = cached.get("series", [])
        seen_years = {row["year"] for row in series}

        logger.info("[%s] fetching landcover %d-%d", name, START_YEAR, END_YEAR)
        for year in range(START_YEAR, END_YEAR + 1):
            if year in seen_years:
                continue
            logger.info("  %d...", year)
            buckets = fetch_year(geometry, year)
            if buckets is None:
                logger.warning("  %d FAILED", year)
                continue
            series.append({"year": year, **buckets})
            # Checkpoint after each successful year so interruptions don't lose work.
            series.sort(key=lambda r: r["year"])
            out_path.write_text(
                json.dumps(
                    {"region_id": region_id, "name": name, "series": series},
                    indent=2,
                )
            )
            time.sleep(3)

        logger.info("[%s] wrote %s (%d years)", name, out_path, len(series))

    logger.info("DONE")


if __name__ == "__main__":
    asyncio.run(main())

"""True-color Landsat basemap tiles via Google Earth Engine.

Returns a MapLibre-compatible `{z}/{x}/{y}` tile-URL template for a
median-composite Landsat image of the given year. We composite over the
May–September window to favor cloud-free growing-season imagery; the
sensor switches per-year to match availability:

- 2013+ → Landsat 8/9 (LC08/LC09 Collection 2 L2)
- 1999–2012 → Landsat 7 (LE07 Collection 2 L2)
- 1984–2012 → Landsat 5 (LT05 Collection 2 L2)

Tile URLs from `getMapId()` expire after a few hours, so this endpoint
is cache-friendly for short intervals but should not be cached server-
side across days.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.services.gee_service import init_gee

logger = logging.getLogger(__name__)

router = APIRouter()

# Three-north shelterbelt viewport — broad enough to cover both Horqin and
# Otindag plus their surroundings.
_SANDBELT_BBOX = [110.0, 40.0, 126.0, 48.0]


def _select_collection(year: int) -> tuple[str, dict]:
    """Return (EE image collection id, surface-reflectance band mapping).

    Band mapping tells us which SR bands map to RGB for true color. The
    collection switches based on which Landsat mission has good coverage
    for the requested year.
    """
    if year >= 2013:
        return (
            "LANDSAT/LC08/C02/T1_L2",
            {"R": "SR_B4", "G": "SR_B3", "B": "SR_B2"},
        )
    if year >= 1999:
        return (
            "LANDSAT/LE07/C02/T1_L2",
            {"R": "SR_B3", "G": "SR_B2", "B": "SR_B1"},
        )
    return (
        "LANDSAT/LT05/C02/T1_L2",
        {"R": "SR_B3", "G": "SR_B2", "B": "SR_B1"},
    )


@router.get("/landsat")
async def landsat_tile_url(
    year: int = Query(..., ge=1984, le=2030, description="Composite year"),
) -> dict:
    """Build an annual median Landsat composite and return its tile URL."""
    try:
        init_gee()
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to init GEE")
        raise HTTPException(status_code=500, detail=f"GEE init failed: {exc}")

    import ee  # noqa: PLC0415 — lazy import matches service pattern

    collection_id, bands = _select_collection(year)
    start = f"{year}-05-01"
    end = f"{year}-09-30"
    roi = ee.Geometry.Rectangle(_SANDBELT_BBOX)

    try:
        # QA_PIXEL bit 3 = cloud, bit 4 = cloud shadow — mask both.
        def _mask_clouds(img: ee.Image) -> ee.Image:
            qa = img.select("QA_PIXEL")
            mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
            scaled = img.select("SR_B.").multiply(0.0000275).add(-0.2)
            return scaled.updateMask(mask).copyProperties(img, ["system:time_start"])

        composite = (
            ee.ImageCollection(collection_id)
            .filterDate(start, end)
            .filterBounds(roi)
            .map(_mask_clouds)
            .median()
        )

        vis = {
            "bands": [bands["R"], bands["G"], bands["B"]],
            "min": 0.03,
            "max": 0.3,
            "gamma": 1.1,
        }
        map_info = composite.getMapId(vis)
        tile_url = map_info["tile_fetcher"].url_format
    except Exception as exc:  # noqa: BLE001
        logger.exception("GEE composite failed for year=%s", year)
        raise HTTPException(
            status_code=502,
            detail=f"GEE composite failed: {exc}",
        )

    return {
        "year": year,
        "collection": collection_id,
        "tile_url": tile_url,
        "attribution": "USGS Landsat / Google Earth Engine",
    }

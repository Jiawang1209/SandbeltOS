"""Pixel-grid NDVI hotspots per region per year.

Serves pre-computed GeoJSON cached on disk at
`backend/data/grids/{region_id}_{year}.geojson`. These are produced by
`scripts/fetch_ndvi_grid.py` and are intended for interactive hotspot
visualization on the map.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GRID_DIR = BACKEND_ROOT / "data" / "grids"


@router.get("/ndvi/{region_id}")
async def get_ndvi_grid(region_id: int, year: int) -> dict:
    """Return the cached NDVI grid GeoJSON for this region/year.

    Clients are expected to render these polygons as a choropleth using the
    `ndvi` property on each feature.
    """
    path = GRID_DIR / f"{region_id}_{year}.geojson"
    if not path.exists():
        raise HTTPException(status_code=404, detail="grid not cached for this region/year")
    with path.open() as fh:
        return json.load(fh)


@router.get("/ndvi/{region_id}/years")
async def list_available_years(region_id: int) -> dict:
    """Report which years are cached for the given region."""
    years: list[int] = []
    for p in GRID_DIR.glob(f"{region_id}_*.geojson"):
        try:
            years.append(int(p.stem.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return {"region_id": region_id, "years": sorted(years)}

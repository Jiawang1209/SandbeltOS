"""Pixel-grid NDVI hotspots per region per year.

Serves pre-computed GeoJSON cached on disk:
  * `backend/data/grids/{region_id}_{year}.geojson`     — MODIS 500m
    native, ~5 km display cells (default)
  * `backend/data/grids/{region_id}_{year}_s2.geojson`  — Sentinel-2
    10m native, ~1 km display cells (when `?source=s2`)

Both are produced by `scripts/fetch_ndvi_grid.py` (MODIS) and
`scripts/fetch_s2_grid.py` (Sentinel-2). The schema is identical so
the frontend can render either with the same code path.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GRID_DIR = BACKEND_ROOT / "data" / "grids"

GridSource = Literal["modis", "s2"]


def _grid_path(region_id: int, year: int, source: GridSource) -> Path:
    suffix = "_s2" if source == "s2" else ""
    return GRID_DIR / f"{region_id}_{year}{suffix}.geojson"


@router.get("/ndvi/{region_id}")
async def get_ndvi_grid(
    region_id: int,
    year: int,
    source: GridSource = Query(
        "modis", description="Sensor cache to read: 'modis' (default) or 's2'."
    ),
) -> dict:
    """Return the cached NDVI grid GeoJSON for this region/year/source.

    Clients render these polygons as a choropleth using the `ndvi`
    property on each feature.
    """
    path = _grid_path(region_id, year, source)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"grid not cached for region {region_id} year {year} source {source}",
        )
    with path.open() as fh:
        return json.load(fh)


@router.get("/ndvi/{region_id}/years")
async def list_available_years(
    region_id: int,
    source: GridSource = Query("modis"),
) -> dict:
    """Report which years are cached for the given (region, source)."""
    pattern = f"{region_id}_*_s2.geojson" if source == "s2" else f"{region_id}_*.geojson"
    years: list[int] = []
    for p in GRID_DIR.glob(pattern):
        try:
            # MODIS stems look like "1_2025"; S2 stems look like "1_2025_s2".
            parts = p.stem.split("_")
            years.append(int(parts[1]))
        except (IndexError, ValueError):
            continue
    # The MODIS glob also matches S2 files (they share the prefix), so
    # de-dup any years that aren't actually MODIS.
    if source == "modis":
        years = [
            int(p.stem.split("_", 1)[1])
            for p in GRID_DIR.glob(f"{region_id}_*.geojson")
            if not p.stem.endswith("_s2")
        ]
    return {"region_id": region_id, "source": source, "years": sorted(set(years))}


@router.get("/ndvi-diff/{region_id}")
async def get_ndvi_grid_diff(
    region_id: int,
    before: int,
    after: int,
    source: GridSource = Query(
        "modis", description="Sensor cache to diff: 'modis' (default) or 's2'."
    ),
) -> dict:
    """Per-cell NDVI diff between two cached years.

    The two cached grids share the same (col, row) integer scheme, so the
    diff is a coordinate-keyed subtraction. Both years must come from the
    same `source` — diffing MODIS against S2 would be apples-to-oranges
    given the different scales and grid sizes.

    Returns a GeoJSON FeatureCollection where each feature carries
    `ndvi_before`, `ndvi_after`, and `diff = after - before`, plus a
    `summary` object with the top-5 gain and top-5 loss cells.
    """
    if before == after:
        raise HTTPException(status_code=400, detail="before and after must differ")

    before_path = _grid_path(region_id, before, source)
    after_path = _grid_path(region_id, after, source)
    for label, path in (("before", before_path), ("after", after_path)):
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"{label} grid not cached for region {region_id} year {before if label == 'before' else after} source {source}",
            )

    with before_path.open() as fh:
        before_fc = json.load(fh)
    with after_path.open() as fh:
        after_fc = json.load(fh)

    # Key by (col, row) — the grid scheme guarantees they match.
    before_by_cell = {
        (f["properties"]["col"], f["properties"]["row"]): f["properties"]["ndvi"]
        for f in before_fc["features"]
    }

    diff_features: list[dict] = []
    for feat in after_fc["features"]:
        props = feat["properties"]
        key = (props["col"], props["row"])
        ndvi_before = before_by_cell.get(key)
        if ndvi_before is None:
            continue  # cell missing in earlier year — skip rather than fabricate a diff
        ndvi_after = props["ndvi"]
        diff_features.append(
            {
                "type": "Feature",
                "geometry": feat["geometry"],
                "properties": {
                    "col": props["col"],
                    "row": props["row"],
                    "ndvi_before": round(ndvi_before, 4),
                    "ndvi_after": round(ndvi_after, 4),
                    "diff": round(ndvi_after - ndvi_before, 4),
                },
            }
        )

    # Top-K gain / loss for the sidebar. Sorted twice rather than once-
    # and-sliced because the population is small (a few hundred cells).
    sorted_by_diff = sorted(diff_features, key=lambda f: f["properties"]["diff"])
    top_loss = [f["properties"] for f in sorted_by_diff[:5]]
    top_gain = [f["properties"] for f in sorted_by_diff[-5:][::-1]]
    diffs = [f["properties"]["diff"] for f in diff_features]
    mean_diff = sum(diffs) / len(diffs) if diffs else 0.0

    return {
        "type": "FeatureCollection",
        "features": diff_features,
        "summary": {
            "region_id": region_id,
            "before_year": before,
            "after_year": after,
            "source": source,
            "n_cells": len(diff_features),
            "mean_diff": round(mean_diff, 4),
            "gain_cells": sum(1 for d in diffs if d > 0.02),
            "loss_cells": sum(1 for d in diffs if d < -0.02),
            "top_gain": top_gain,
            "top_loss": top_loss,
        },
    }

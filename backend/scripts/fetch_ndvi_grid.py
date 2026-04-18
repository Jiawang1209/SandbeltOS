"""
Fetch a coarse NDVI grid for each sandy-land subregion from MODIS MOD13A1.

For each region polygon we walk a regular lon/lat grid (default 5 km) clipped
to the polygon, and sample annual-mean NDVI for each year. Output is one
GeoJSON FeatureCollection per (region_id, year) under
`backend/data/grids/{region_id}_{year}.geojson`.

Run once per year; cache is cheap to serve from the API afterwards.

Usage:
    python -m backend.scripts.fetch_ndvi_grid --years 2015 2020 2025 --step-km 5
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from app.config import get_settings
from app.services.gee_service import init_gee

BACKEND_ROOT = Path(__file__).resolve().parent.parent
GRID_DIR = BACKEND_ROOT / "data" / "grids"

# MODIS MOD13A1 native resolution is ~500m; we aggregate up to a coarser grid
# for interactive display (fewer polygons → fast MapLibre render).
SAMPLE_SCALE = 500


def _polygon_bounds(geom: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return (west, south, east, north) from a (Multi)Polygon GeoJSON."""
    coords = geom["coordinates"]
    if geom["type"] == "MultiPolygon":
        rings = [ring for poly in coords for ring in poly]
    else:
        rings = coords
    xs: list[float] = []
    ys: list[float] = []
    for ring in rings:
        for x, y in ring:
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def _build_cells(
    geom: dict[str, Any], step_km: float
) -> list[dict[str, Any]]:
    """Grid the polygon bbox at ~step_km spacing; return list of cell dicts."""
    west, south, east, north = _polygon_bounds(geom)

    # Approx: 1° lat ≈ 111 km; 1° lon ≈ 111 * cos(lat).
    mean_lat = (south + north) / 2
    dlat = step_km / 111.0
    dlon = step_km / (111.0 * max(math.cos(math.radians(mean_lat)), 0.1))

    cells: list[dict[str, Any]] = []
    lat = south
    row = 0
    while lat < north:
        lon = west
        col = 0
        while lon < east:
            cells.append({
                "col": col,
                "row": row,
                "w": lon,
                "s": lat,
                "e": lon + dlon,
                "n": lat + dlat,
            })
            lon += dlon
            col += 1
        lat += dlat
        row += 1
    return cells


def _sample_grid_ndvi(
    region_geom: dict[str, Any],
    cells: list[dict[str, Any]],
    year: int,
) -> list[dict[str, Any]]:
    """Batch-sample annual-mean NDVI for each cell via GEE reduceRegion."""
    import ee  # type: ignore

    # Build an annual mean image.
    coll = (
        ee.ImageCollection("MODIS/061/MOD13A1")
        .filterDate(f"{year}-01-01", f"{year + 1}-01-01")
        .select("NDVI")
    )
    annual = coll.mean().multiply(0.0001)
    roi = ee.Geometry(region_geom)
    annual = annual.clip(roi)

    # Build one FeatureCollection of cell rectangles, intersected with roi.
    features = []
    for c in cells:
        rect = ee.Geometry.Rectangle([c["w"], c["s"], c["e"], c["n"]])
        clipped = rect.intersection(roi, 1)
        f = ee.Feature(clipped, {
            "col": c["col"],
            "row": c["row"],
            "w": c["w"],
            "s": c["s"],
            "e": c["e"],
            "n": c["n"],
        })
        features.append(f)
    fc = ee.FeatureCollection(features)

    # reduceRegions: mean NDVI per feature.
    reduced = annual.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=SAMPLE_SCALE,
    )
    info = reduced.getInfo()

    out: list[dict[str, Any]] = []
    for feat in info.get("features", []):
        props = feat.get("properties", {})
        mean = props.get("mean")
        if mean is None:
            continue
        out.append({
            "col": props["col"],
            "row": props["row"],
            "w": props["w"],
            "s": props["s"],
            "e": props["e"],
            "n": props["n"],
            "ndvi": float(mean),
        })
    return out


def _cells_to_geojson(cells: list[dict[str, Any]]) -> dict[str, Any]:
    features = []
    for c in cells:
        features.append({
            "type": "Feature",
            "properties": {
                "col": c["col"],
                "row": c["row"],
                "ndvi": round(c["ndvi"], 4),
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [c["w"], c["s"]],
                    [c["e"], c["s"]],
                    [c["e"], c["n"]],
                    [c["w"], c["n"]],
                    [c["w"], c["s"]],
                ]],
            },
        })
    return {"type": "FeatureCollection", "features": features}


def _fetch_subregions() -> list[tuple[int, str, dict[str, Any]]]:
    """Load subregion polygons from Postgres."""
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, name, bbox_json FROM regions "
            "WHERE level = 'subregion' ORDER BY id"
        )).fetchall()
    out: list[tuple[int, str, dict[str, Any]]] = []
    for rid, name, bbox in rows:
        if bbox is None:
            continue
        geom = json.loads(bbox) if isinstance(bbox, str) else bbox
        if "coordinates" not in geom:
            # bbox shortcut — convert to polygon
            n, s, e, w = geom["north"], geom["south"], geom["east"], geom["west"]
            geom = {
                "type": "Polygon",
                "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
            }
        out.append((rid, name, geom))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, default=[2015, 2020, 2025])
    parser.add_argument("--step-km", type=float, default=5.0)
    parser.add_argument("--region-id", type=int, default=None, help="Restrict to one region")
    args = parser.parse_args()

    init_gee()

    GRID_DIR.mkdir(parents=True, exist_ok=True)
    subregions = _fetch_subregions()
    print(f"[grid] {len(subregions)} subregions loaded")

    for rid, name, geom in subregions:
        if args.region_id and rid != args.region_id:
            continue
        cells = _build_cells(geom, step_km=args.step_km)
        print(f"[grid] region {rid} ({name}): {len(cells)} cells at {args.step_km} km")
        for year in args.years:
            out_path = GRID_DIR / f"{rid}_{year}.geojson"
            if out_path.exists():
                print(f"[grid]   {year} cached at {out_path.name}")
                continue
            print(f"[grid]   sampling {year} …")
            sampled = _sample_grid_ndvi(geom, cells, year)
            gj = _cells_to_geojson(sampled)
            out_path.write_text(json.dumps(gj))
            print(f"[grid]   {year} → {len(sampled)} cells → {out_path.name}")


if __name__ == "__main__":
    main()

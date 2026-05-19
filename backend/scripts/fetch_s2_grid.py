"""Fetch a finer NDVI grid for each sandy-land subregion from Sentinel-2.

Native S2 resolution is 10m (B4 red + B8 NIR), but we still aggregate up
to a regular display grid for MapLibre — at 10m native, two sandy lands
of 50,000+ km² would be ~500M pixels each, far past what a polygon
overlay can render interactively.

The choice of `--step-km 1` (1km cells) is a deliberate sweet spot:
  * **5× finer than MODIS** (MODIS fetcher defaults to 5km cells from
    500m native), so the difference shows visually
  * Each cell still samples from many true 10m pixels, so the value
    reflects S2's higher signal-to-noise even though the display unit
    is 1km
  * File size stays under ~500KB per (region, year), browser-friendly

Pipeline:
  1. Filter `COPERNICUS/S2_SR_HARMONIZED` to the growing season
     (Jun-Sep) of the requested year and `CLOUDY_PIXEL_PERCENTAGE < 20`.
  2. Per image, mask clouds + cirrus via the QA60 band.
  3. Compute NDVI = (B8 - B4) / (B8 + B4), take a per-pixel median
     across the season — robust to remaining cloud edges.
  4. `reduceRegions(mean)` per 1km cell.

Output: `backend/data/grids/{region_id}_{year}_s2.geojson` — same
schema as the MODIS grids (`{col, row, ndvi}` properties), so the
existing diff + hotspot rendering paths work unchanged with just a
source-suffix flip.

Usage:
    python -m scripts.fetch_s2_grid --years 2020 2025 --step-km 1
    python -m scripts.fetch_s2_grid --years 2025 --region-id 1 --step-km 0.5
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

# Defer heavy imports so --help works without the full backend env.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

GRID_DIR = _BACKEND_ROOT / "data" / "grids"

# Sentinel-2 native resolution for B4 + B8 (the bands we use).
SAMPLE_SCALE = 10

# Growing season for the three-north shelterbelt latitudes.
GROWING_SEASON_MONTHS = (6, 9)

# Cloud-pixel percentage threshold for scene-level filtering. Below 20%
# is a generous floor that still keeps a useful image count per season.
MAX_CLOUDY_PCT = 20


def _polygon_bounds(geom: dict[str, Any]) -> tuple[float, float, float, float]:
    coords = geom["coordinates"]
    rings = (
        [ring for poly in coords for ring in poly]
        if geom["type"] == "MultiPolygon"
        else coords
    )
    xs: list[float] = []
    ys: list[float] = []
    for ring in rings:
        for x, y in ring:
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def _build_cells(geom: dict[str, Any], step_km: float) -> list[dict[str, Any]]:
    west, south, east, north = _polygon_bounds(geom)
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


def _build_s2_ndvi_image(year: int, roi):  # roi: ee.Geometry
    """Median-composite NDVI from S2 SR over the growing season of `year`."""
    import ee  # noqa: PLC0415

    def mask_clouds(img):
        # QA60 bit 10 = opaque clouds, bit 11 = cirrus. Mask both.
        qa = img.select("QA60")
        mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
        return img.updateMask(mask)

    coll = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(f"{year}-{GROWING_SEASON_MONTHS[0]:02d}-01",
                    f"{year}-{GROWING_SEASON_MONTHS[1]:02d}-30")
        .filterBounds(roi)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUDY_PCT))
        .map(mask_clouds)
    )

    def add_ndvi(img):
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
        return img.addBands(ndvi)

    return coll.map(add_ndvi).select("NDVI").median().clip(roi)


def _sample_grid_ndvi(
    region_geom: dict[str, Any],
    cells: list[dict[str, Any]],
    year: int,
) -> list[dict[str, Any]]:
    import ee  # noqa: PLC0415

    roi = ee.Geometry(region_geom)
    ndvi_img = _build_s2_ndvi_image(year, roi)

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

    reduced = ndvi_img.reduceRegions(
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
    from sqlalchemy import create_engine, text  # noqa: PLC0415
    from app.config import get_settings  # noqa: PLC0415

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
            n, s, e, w = geom["north"], geom["south"], geom["east"], geom["west"]
            geom = {
                "type": "Polygon",
                "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
            }
        out.append((rid, name, geom))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=[2020, 2025])
    parser.add_argument(
        "--step-km",
        type=float,
        default=1.0,
        help="Grid cell size in km (default 1.0 = 5× MODIS resolution).",
    )
    parser.add_argument("--region-id", type=int, default=None)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-sample even if the output file already exists.",
    )
    args = parser.parse_args()

    from app.services.gee_service import init_gee  # noqa: PLC0415
    init_gee()

    GRID_DIR.mkdir(parents=True, exist_ok=True)
    subregions = _fetch_subregions()
    print(f"[s2-grid] {len(subregions)} subregions loaded", flush=True)

    for rid, name, geom in subregions:
        if args.region_id and rid != args.region_id:
            continue
        cells = _build_cells(geom, step_km=args.step_km)
        print(
            f"[s2-grid] region {rid} ({name}): {len(cells)} cells at "
            f"{args.step_km} km",
            flush=True,
        )
        for year in args.years:
            out_path = GRID_DIR / f"{rid}_{year}_s2.geojson"
            if out_path.exists() and not args.force:
                print(f"[s2-grid]   {year} cached at {out_path.name}", flush=True)
                continue
            print(f"[s2-grid]   sampling {year} …", flush=True)
            sampled = _sample_grid_ndvi(geom, cells, year)
            gj = _cells_to_geojson(sampled)
            out_path.write_text(json.dumps(gj))
            print(
                f"[s2-grid]   {year} → {len(sampled)} cells → {out_path.name}",
                flush=True,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())

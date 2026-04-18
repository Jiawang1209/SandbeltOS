"""Derive Horqin / Otindag sandy-land outlines from GEE remote-sensing data.

Sandy land (沙地) = barren + sparse / low-NDVI grassland inside the authoritative
bbox envelope. Specifically:
- ESA WorldCover 2021 class 60 (Bare / sparse vegetation)
- Plus class 30 (Grassland) AND mean 2022 NDVI < 0.35
  → captures semi-fixed / fixed sandy grassland that visually matches "沙地"

Output is saved to regions.bbox_json as a MultiPolygon.

Authoritative size reference:
- Horqin  (科尔沁沙地):  ~50,600 km²
- Otindag (浑善达克沙地): ~21,400 km²

Usage:
    cd backend
    PYTHONPATH=. /Users/liuyue/miniforge3/envs/sandbelt/bin/python \
        scripts/seed_gee_sandy.py
"""
from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

import ee
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid
from sqlalchemy import text

from app.database import async_session as AsyncSessionLocal

GEE_PROJECT = "ee-yueliu19921209"

# Tight envelopes — only inside these do we look for sandy-land pixels.
HORQIN_BBOX = (119.0, 42.3, 123.0, 44.0)   # West Liaohe basin
OTINDAG_BBOX = (113.5, 41.7, 117.1, 43.2)  # southern Xilingol

# Scale for vectorization (meters). 500m = MODIS-ish detail; keeps getInfo small.
VECTOR_SCALE = 500

# Summer-max NDVI threshold for "sparse grass = sandy grass":
#   flowing sand       < 0.20
#   semi-fixed dunes   0.20–0.35
#   fixed sandy grass  0.35–0.45
#   healthy grassland  0.45+
# 0.45 captures fixed sandy grass without pulling in true grassland.
NDVI_THRESHOLD = 0.45

CACHE_DIR = Path("/tmp/gee_sand")
CACHE_DIR.mkdir(exist_ok=True)


def sandy_mask(
    bbox: tuple[float, float, float, float],
    include_cropland: bool = False,
) -> ee.Image:
    minlng, minlat, maxlng, maxlat = bbox
    region = ee.Geometry.Rectangle([minlng, minlat, maxlng, maxlat])

    wc = ee.ImageCollection("ESA/WorldCover/v200").first().clip(region)
    bare = wc.eq(60)
    grass = wc.eq(30)
    # Cropland inside a sandy-land envelope = historically sandy land that has
    # been reclaimed; still part of the ecological monitoring zone.
    cropland = wc.eq(40)

    # Summer-max NDVI (Jun15–Aug31) from MODIS 16-day composites, 2020–2022
    # average to smooth yearly drought variability.
    ndvi = (
        ee.ImageCollection("MODIS/061/MOD13Q1")
        .filter(ee.Filter.calendarRange(6, 8, "month"))
        .filterDate("2020-06-01", "2022-09-01")
        .select("NDVI")
        .max()
        .multiply(0.0001)
        .clip(region)
    )
    sparse_grass = grass.And(ndvi.lt(NDVI_THRESHOLD))

    combined = bare.Or(sparse_grass)
    if include_cropland:
        combined = combined.Or(cropland)
    mask = combined.rename("sand").selfMask()

    # Light morphological closing (1-px dilate + erode) — just enough to bridge
    # salt-and-pepper noise, not merge distant patches.
    k = ee.Kernel.square(radius=1, units="pixels")
    mask = mask.unmask(0).focal_max(kernel=k).focal_min(kernel=k).selfMask()

    return mask


def vectorize(mask: ee.Image, bbox: tuple[float, float, float, float]) -> dict:
    minlng, minlat, maxlng, maxlat = bbox
    region = ee.Geometry.Rectangle([minlng, minlat, maxlng, maxlat])
    vectors = mask.reduceToVectors(
        geometry=region,
        scale=VECTOR_SCALE,
        geometryType="polygon",
        eightConnected=True,
        labelProperty="sand",
        maxPixels=1e10,
        bestEffort=False,
    )
    return vectors.getInfo()


def geojson_to_multipoly(fc: dict, min_area_km2: float = 2.0) -> MultiPolygon:
    polys: list[Polygon] = []
    for f in fc.get("features", []):
        g = shape(f["geometry"])
        if not g.is_valid:
            g = make_valid(g)
        geoms = [g] if isinstance(g, Polygon) else list(getattr(g, "geoms", []))
        for p in geoms:
            if not isinstance(p, Polygon) or p.is_empty:
                continue
            minx, miny, maxx, maxy = p.bounds
            mean_lat = (miny + maxy) / 2
            km2 = p.area * (111.32 ** 2) * math.cos(math.radians(mean_lat))
            if km2 >= min_area_km2:
                polys.append(p)

    if not polys:
        return MultiPolygon()
    merged = unary_union(polys)
    if isinstance(merged, Polygon):
        return MultiPolygon([merged])
    if isinstance(merged, MultiPolygon):
        return merged
    return MultiPolygon([p for p in getattr(merged, "geoms", []) if isinstance(p, Polygon)])


def smooth_outline(geom: MultiPolygon, buffer_km: float = 8.0,
                   keep_top_n: int = 3) -> MultiPolygon:
    """Dilate + erode to produce a single continuous outline of the sandy-land
    ecological zone (professional maps show this, not raw pixel patches).
    Then keep only the top-N largest connected components.
    """
    if geom.is_empty:
        return geom
    # Convert km → degrees at the geom's mean lat
    minx, miny, maxx, maxy = geom.bounds
    mean_lat = (miny + maxy) / 2
    deg_per_km = 1.0 / (111.32 * math.cos(math.radians(mean_lat)))
    buf = buffer_km * deg_per_km

    dilated = geom.buffer(buf, join_style=1)        # round joins
    closed = dilated.buffer(-buf, join_style=1)     # symmetric erode → area-preserving

    if closed.is_empty:
        return MultiPolygon()
    if isinstance(closed, Polygon):
        parts = [closed]
    else:
        parts = [g for g in getattr(closed, "geoms", []) if isinstance(g, Polygon)]

    # Rank by area, keep top N
    parts.sort(key=lambda p: p.area, reverse=True)
    parts = parts[:keep_top_n]
    # Drop parts < 5% of the largest
    if parts:
        cutoff = parts[0].area * 0.05
        parts = [p for p in parts if p.area >= cutoff]
    return MultiPolygon(parts) if parts else MultiPolygon()


def area_km2(geom) -> float:
    if geom.is_empty:
        return 0.0
    minx, miny, maxx, maxy = geom.bounds
    mean_lat = (miny + maxy) / 2
    return geom.area * (111.32 ** 2) * math.cos(math.radians(mean_lat))


def to_mp_geojson(geom: MultiPolygon) -> dict:
    if geom.is_empty:
        return {"type": "MultiPolygon", "coordinates": []}
    gj = mapping(geom)
    if gj["type"] == "Polygon":
        gj = {"type": "MultiPolygon", "coordinates": [gj["coordinates"]]}
    return gj


async def main() -> None:
    ee.Initialize(project=GEE_PROJECT)

    targets = [
        # (id, name, bbox, slug, expected_km2, include_cropland)
        # Horqin is in West Liaohe basin — much of historical sandy land has
        # been reclaimed to cropland; include it to match the ecological zone.
        # Otindag sits on Xilingol grassland with little cropland; don't.
        (1, "科尔沁沙地", HORQIN_BBOX, "horqin", 50_600, True),
        (2, "浑善达克沙地", OTINDAG_BBOX, "otindag", 21_400, False),
    ]

    results: dict[int, tuple[dict, float]] = {}

    for region_id, name, bbox, slug, expected, incl_crop in targets:
        cache = CACHE_DIR / f"{slug}_v2.json"
        if cache.exists():
            print(f"[{name}] using cached vectors")
            fc = json.loads(cache.read_text())
        else:
            print(f"[{name}] computing GEE mask + vectorizing "
                  f"(scale={VECTOR_SCALE}m, cropland={incl_crop})...")
            mask = sandy_mask(bbox, include_cropland=incl_crop)
            fc = vectorize(mask, bbox)
            cache.write_text(json.dumps(fc))
            print(f"  raw features: {len(fc.get('features', []))}")

        mp = geojson_to_multipoly(fc)
        # Close gaps between scattered patches → single ecological outline
        smoothed = smooth_outline(mp, buffer_km=3.0, keep_top_n=3)
        # Simplify ~500m for lighter payload
        simp = smoothed.simplify(0.005, preserve_topology=True)
        if isinstance(simp, Polygon):
            simp = MultiPolygon([simp])

        km2 = area_km2(simp)
        n = len(simp.geoms) if not simp.is_empty else 0
        print(f"  polygons: {n}, area: {km2:,.0f} km² "
              f"(expected ~{expected:,}, ratio={km2/expected:.2f}x)")
        results[region_id] = (to_mp_geojson(simp), km2)

    async with AsyncSessionLocal() as session:
        for region_id, (gj, km2) in results.items():
            await session.execute(
                text("UPDATE regions SET bbox_json = :g, area_km2 = :a WHERE id = :i"),
                {"g": json.dumps(gj), "a": km2, "i": region_id},
            )
        await session.commit()
        print("\nDB updated.")

        rows = (await session.execute(
            text("SELECT id, name, area_km2, "
                 "jsonb_array_length(bbox_json->'coordinates') AS n "
                 "FROM regions WHERE level='subregion' ORDER BY id")
        )).fetchall()
        for r in rows:
            print(f"  region {r[0]} {r[1]}: {r[2]:,.0f} km², {r[3]} polygons")


if __name__ == "__main__":
    asyncio.run(main())

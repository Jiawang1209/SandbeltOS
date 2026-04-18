"""Replace regions.bbox_json with OSM natural=sand polygons for the two sandy
lands. OSM is the only free, globally-accessible vector source that actually
mapped these boundaries.

Authoritative size reference (for validation):
- Horqin (科尔沁沙地):  ~50,600 km²  (China's largest sandy land)
- Otindag (浑善达克沙地): ~21,400 km²

Usage:
    cd backend
    PYTHONPATH=. /Users/liuyue/miniforge3/envs/sandbelt/bin/python \
        scripts/seed_osm_sandy.py
"""
from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

import requests
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid
from sqlalchemy import text

from app.database import async_session as AsyncSessionLocal

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Generous bbox per region — OSM polygons are clipped to actual sand extent.
HORQIN_BBOX = (118.0, 42.0, 123.0, 44.0)   # (minLng, minLat, maxLng, maxLat)
OTINDAG_BBOX = (113.0, 41.5, 117.5, 43.5)

CACHE_DIR = Path("/tmp/osm_sand")
CACHE_DIR.mkdir(exist_ok=True)


def overpass_query(bbox: tuple[float, float, float, float]) -> dict:
    minlng, minlat, maxlng, maxlat = bbox
    q = f"""
[out:json][timeout:120];
(
  way["natural"="sand"]({minlat},{minlng},{maxlat},{maxlng});
  relation["natural"="sand"]({minlat},{minlng},{maxlat},{maxlng});
);
out geom;
""".strip()
    r = requests.post(OVERPASS_URL, data={"data": q}, timeout=180)
    r.raise_for_status()
    return r.json()


def way_to_polygon(way: dict) -> Polygon | None:
    coords = [(n["lon"], n["lat"]) for n in way.get("geometry", [])]
    if len(coords) < 4 or coords[0] != coords[-1]:
        if len(coords) >= 3:
            coords.append(coords[0])
        else:
            return None
    try:
        poly = Polygon(coords)
        if not poly.is_valid:
            poly = make_valid(poly)
        return poly if not poly.is_empty else None
    except Exception:
        return None


def relation_to_polygons(rel: dict) -> list[Polygon]:
    # Multipolygon relations have outer/inner rings in members[*].geometry
    outers: list[list[tuple[float, float]]] = []
    inners: list[list[tuple[float, float]]] = []
    for m in rel.get("members", []):
        if m.get("type") != "way":
            continue
        coords = [(n["lon"], n["lat"]) for n in m.get("geometry", [])]
        if len(coords) < 3:
            continue
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        role = m.get("role", "")
        (outers if role != "inner" else inners).append(coords)

    polys: list[Polygon] = []
    for out in outers:
        holes = [h for h in inners if Polygon(out).contains(Polygon(h).representative_point())]
        try:
            p = Polygon(out, holes)
            if not p.is_valid:
                p = make_valid(p)
            if not p.is_empty:
                polys.append(p)
        except Exception:
            continue
    return polys


def collect_geometry(data: dict) -> MultiPolygon:
    polys: list[Polygon] = []
    for e in data.get("elements", []):
        if e["type"] == "way":
            p = way_to_polygon(e)
            if p:
                polys.append(p)
        elif e["type"] == "relation":
            polys.extend(relation_to_polygons(e))

    if not polys:
        return MultiPolygon()

    merged = unary_union(polys)
    if isinstance(merged, Polygon):
        return MultiPolygon([merged])
    if isinstance(merged, MultiPolygon):
        return merged
    # GeometryCollection fallback
    out: list[Polygon] = []
    for g in merged.geoms:
        if isinstance(g, Polygon):
            out.append(g)
        elif isinstance(g, MultiPolygon):
            out.extend(g.geoms)
    return MultiPolygon(out)


def area_km2(geom) -> float:
    if geom.is_empty:
        return 0.0
    minx, miny, maxx, maxy = geom.bounds
    mean_lat = (miny + maxy) / 2
    return geom.area * (111.32 ** 2) * math.cos(math.radians(mean_lat))


def to_multipolygon_geojson(geom: MultiPolygon) -> dict:
    if geom.is_empty:
        return {"type": "MultiPolygon", "coordinates": []}
    gj = mapping(geom)
    if gj["type"] == "Polygon":
        gj = {"type": "MultiPolygon", "coordinates": [gj["coordinates"]]}
    return gj


async def main() -> None:
    targets = [
        (1, "科尔沁沙地", HORQIN_BBOX, "horqin", 50_600),
        (2, "浑善达克沙地", OTINDAG_BBOX, "otindag", 21_400),
    ]

    results: dict[int, tuple[dict, float]] = {}

    for region_id, name, bbox, slug, expected_km2 in targets:
        cache = CACHE_DIR / f"{slug}.json"
        if cache.exists():
            print(f"[{name}] using cached Overpass response")
            data = json.loads(cache.read_text())
        else:
            print(f"[{name}] querying Overpass...")
            data = overpass_query(bbox)
            cache.write_text(json.dumps(data))

        geom = collect_geometry(data)
        simplified = geom.simplify(0.002, preserve_topology=True)  # ~200m tolerance
        if isinstance(simplified, Polygon):
            simplified = MultiPolygon([simplified])

        km2 = area_km2(simplified)
        n = len(simplified.geoms) if not simplified.is_empty else 0
        print(f"  polygons: {n}, area: {km2:,.0f} km² "
              f"(expected ~{expected_km2:,} km², ratio={km2/expected_km2:.2f}x)")
        results[region_id] = (to_multipolygon_geojson(simplified), km2)

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

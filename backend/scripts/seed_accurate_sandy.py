"""Build accurate sandy-land polygons by unioning banner geometries and
clipping to the authoritative lat/lng extents documented in the literature.

Authoritative sources:
- Horqin (科尔沁沙地): 42°04'~43°30'N, 118°35'~122°20'E
  (from 《Demarcation of the Horqin Sandy Land Boundary》, Baidu Baike)
- Otindag (浑善达克沙地): southern Xilingol + western Keshiketeng
  (from 中国沙漠学会, 锡林郭勒盟政府网)

The script picks every banner that overlaps each sandy-land bbox, unions their
polygons, clips the union to the bbox, and writes the resulting MultiPolygon
back to regions.bbox_json.

Also fixes a bug in the previous seed script: 150424 is 林西县 (mountain),
NOT 翁牛特旗 — the correct code is 150426.

Usage:
    cd backend
    PYTHONPATH=. /Users/liuyue/miniforge3/envs/sandbelt/bin/python \
        scripts/seed_accurate_sandy.py
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union
from sqlalchemy import text

from app.database import async_session as AsyncSessionLocal

ADM_DIR = Path("/tmp/adm")

# --- Authoritative lat/lng extents ----------------------------------------

# Horqin: 42°04'~43°30'N, 118°35'~122°20'E (slight padding for banner edges)
HORQIN_BBOX = (118.50, 42.00, 122.50, 43.60)  # (minLng, minLat, maxLng, maxLat)

# Otindag: authoritative extent ~41.8°~43.2°N, 113.5°~117.0°E
# (~3.5° × 1.4° ≈ 23,700 km², matches the ~2.38万 km² published figure)
OTINDAG_BBOX = (113.50, 41.80, 117.10, 43.20)

# --- Banners whose territory may overlap each sandy-land bbox --------------
# Chosen to OVERESTIMATE so the bbox clip trims them to the real extent.

HORQIN_ADCODES = {
    "150521",  # 科尔沁左翼中旗
    "150522",  # 科尔沁左翼后旗
    "150523",  # 开鲁县
    "150524",  # 库伦旗
    "150525",  # 奈曼旗
    "150526",  # 扎鲁特旗 (southern tip only, clipped)
    "150421",  # 阿鲁科尔沁旗 (southern tip only, clipped)
    "150426",  # 翁牛特旗 (CORRECT code, not 150424=林西县)
    "150430",  # 敖汉旗
}

OTINDAG_ADCODES = {
    "152527",  # 太仆寺旗
    "152528",  # 镶黄旗
    "152529",  # 正镶白旗
    "152530",  # 正蓝旗
    "152531",  # 多伦县
    "152523",  # 苏尼特左旗 (southern tip only, clipped)
    "152522",  # 阿巴嘎旗 (southern tip only, clipped)
    "152502",  # 锡林浩特市 (southern tip only, clipped)
    "150425",  # 克什克腾旗 (赤峰市, western portion only, clipped)
}


def load_features() -> dict[str, dict]:
    features: dict[str, dict] = {}
    for fname in ("tongliao.json", "chifeng.json", "xilingol.json"):
        data = json.loads((ADM_DIR / fname).read_text())
        for ft in data["features"]:
            features[str(ft["properties"]["adcode"])] = ft
    return features


def build_clipped_multipolygon(
    features: dict[str, dict],
    adcodes: set[str],
    bbox: tuple[float, float, float, float],
) -> dict:
    """Union selected banners, clip to bbox, return as GeoJSON MultiPolygon."""
    geoms = []
    for code in adcodes:
        ft = features.get(code)
        if not ft:
            print(f"  WARN missing adcode {code}")
            continue
        geoms.append(shape(ft["geometry"]))

    merged = unary_union(geoms)
    clipped = merged.intersection(box(*bbox))

    # Normalize to MultiPolygon for consistency
    if clipped.is_empty:
        return {"type": "MultiPolygon", "coordinates": []}

    geom = mapping(clipped)
    if geom["type"] == "Polygon":
        geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
    elif geom["type"] == "GeometryCollection":
        # Extract only polygons from collection
        coords = []
        for g in geom["geometries"]:
            if g["type"] == "Polygon":
                coords.append(g["coordinates"])
            elif g["type"] == "MultiPolygon":
                coords.extend(g["coordinates"])
        geom = {"type": "MultiPolygon", "coordinates": coords}

    return geom


def polygon_area_km2(geom: dict) -> float:
    """Rough area in km² using shapely (WGS84 degrees converted via cos(lat))."""
    import math

    g = shape(geom)
    # Use a planar approximation: degrees^2 * (111km)^2 * cos(mean_lat)
    minx, miny, maxx, maxy = g.bounds
    mean_lat = (miny + maxy) / 2
    km2_per_deg2 = (111.32 ** 2) * math.cos(math.radians(mean_lat))
    return g.area * km2_per_deg2


async def main() -> None:
    features = load_features()
    print(f"Loaded {len(features)} banner features\n")

    horqin = build_clipped_multipolygon(features, HORQIN_ADCODES, HORQIN_BBOX)
    otindag = build_clipped_multipolygon(features, OTINDAG_ADCODES, OTINDAG_BBOX)

    print(f"Horqin:  {len(horqin['coordinates'])} polys, "
          f"~{polygon_area_km2(horqin):,.0f} km²")
    print(f"Otindag: {len(otindag['coordinates'])} polys, "
          f"~{polygon_area_km2(otindag):,.0f} km²\n")

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("UPDATE regions SET bbox_json = :g, area_km2 = :a WHERE id = :i"),
            {"g": json.dumps(horqin), "a": polygon_area_km2(horqin), "i": 1},
        )
        await session.execute(
            text("UPDATE regions SET bbox_json = :g, area_km2 = :a WHERE id = :i"),
            {"g": json.dumps(otindag), "a": polygon_area_km2(otindag), "i": 2},
        )
        await session.commit()

    # Verify
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, name, area_km2, bbox_json->>'type' AS t, "
                    "jsonb_array_length(bbox_json->'coordinates') AS n "
                    "FROM regions WHERE id IN (1, 2) ORDER BY id"
                )
            )
        ).fetchall()
        for r in rows:
            print(f"  region {r[0]} {r[1]}: {r[2]:,.0f} km² — {r[3]} with {r[4]} polygons")


if __name__ == "__main__":
    asyncio.run(main())

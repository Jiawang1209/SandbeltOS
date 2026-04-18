"""Extract real sandy-land boundaries from MODIS NDVI.

Within each region's administrative extent (regions.bbox_json), compute the
multi-year growing-season (Jun-Sep, 2020-2023) mean NDVI from MOD13A1 and
classify pixels with NDVI < NDVI_THRESHOLD as bare/sandy. Vectorize at 500m,
filter tiny polygons, simplify, and overwrite regions.bbox_json with the
resulting MultiPolygon.

Usage (inside backend/):
    https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 \
    conda run -n sandbelt python -m scripts.extract_sandy_boundary
"""
from __future__ import annotations

import asyncio
import json

import ee
from sqlalchemy import text

from app.database import async_session

GEE_PROJECT = "ee-yueliu19921209"
NDVI_THRESHOLD = 0.48  # includes semi-fixed sandy land (not just active bare sand)
MIN_AREA_KM2 = 25.0  # drop small noise fragments
SIMPLIFY_M = 800  # geometry simplification tolerance
SCALE_M = 500  # MOD13A1 native resolution


async def load_admin_geom(region_id: int) -> dict:
    async with async_session() as session:
        result = await session.execute(
            text("SELECT bbox_json FROM regions WHERE id = :i"),
            {"i": region_id},
        )
        row = result.fetchone()
        if row is None or row[0] is None:
            raise RuntimeError(f"region {region_id} missing bbox_json")
        raw = row[0]
        return json.loads(raw) if isinstance(raw, str) else raw


def extract_sandy_multipolygon(admin_geom: dict) -> dict:
    ee_geom = ee.Geometry(admin_geom)

    ndvi = (
        ee.ImageCollection("MODIS/061/MOD13A1")
        .filterDate("2020-06-01", "2023-09-30")
        .filter(ee.Filter.calendarRange(6, 9, "month"))
        .select("NDVI")
        .mean()
        .multiply(0.0001)
    )

    sandy_mask = ndvi.lt(NDVI_THRESHOLD).selfMask().rename("sandy").toInt()

    vectors = sandy_mask.reduceToVectors(
        geometry=ee_geom,
        scale=SCALE_M,
        geometryType="polygon",
        eightConnected=True,
        maxPixels=1e10,
        bestEffort=True,
    )

    # Add area, drop small noise polygons, simplify, clip to admin extent
    vectors = (
        vectors.map(lambda f: f.set("area_km2", f.area(10).divide(1e6)))
        .filter(ee.Filter.gt("area_km2", MIN_AREA_KM2))
        .map(lambda f: f.simplify(maxError=SIMPLIFY_M).intersection(ee_geom, 10))
    )

    fc = vectors.getInfo()
    polys: list = []
    for feat in fc["features"]:
        geom = feat.get("geometry")
        if not geom:
            continue
        if geom["type"] == "Polygon":
            polys.append(geom["coordinates"])
        elif geom["type"] == "MultiPolygon":
            polys.extend(geom["coordinates"])

    return {"type": "MultiPolygon", "coordinates": polys}


async def main() -> None:
    ee.Initialize(project=GEE_PROJECT)
    print("GEE initialized\n", flush=True)

    for region_id, name in [(1, "科尔沁沙地"), (2, "浑善达克沙地")]:
        print(f"=== [{name}] ===", flush=True)
        admin = await load_admin_geom(region_id)
        print(f"  admin geometry: {admin['type']}", flush=True)

        geom = extract_sandy_multipolygon(admin)
        print(f"  sandy MultiPolygon: {len(geom['coordinates'])} polygons", flush=True)

        if not geom["coordinates"]:
            print("  WARN: no sandy pixels found — skipping DB update", flush=True)
            continue

        async with async_session() as session:
            await session.execute(
                text("UPDATE regions SET bbox_json = :g WHERE id = :i"),
                {"g": json.dumps(geom), "i": region_id},
            )
            await session.commit()
        print("  DB updated\n", flush=True)

    # Verify
    async with async_session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, name, bbox_json->>'type' AS t, "
                    "jsonb_array_length(bbox_json->'coordinates') AS n "
                    "FROM regions WHERE id IN (1, 2) ORDER BY id"
                )
            )
        ).fetchall()
        for r in rows:
            print(f"  region {r[0]} {r[1]}: {r[2]} with {r[3]} polygons", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

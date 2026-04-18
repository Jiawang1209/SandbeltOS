"""Update regions.bbox_json with hand-curated natural polygons for the two sandy lands.

Based on published extent maps of 科尔沁沙地 and 浑善达克沙地. Shapes are
intentionally irregular (not rectangles) to convey real geographic boundaries.
"""
from __future__ import annotations

import asyncio
import json

from sqlalchemy import text

from app.database import async_session as AsyncSessionLocal


# 科尔沁沙地 (Horqin): elongated NE-SW, ~42,300 km², spans Tongliao/Chifeng/Ar Horqin.
# Clockwise from NW corner.
HORQIN_COORDS = [
    [119.55, 44.75],
    [120.30, 44.95],
    [121.10, 45.05],
    [122.15, 44.88],
    [123.10, 44.70],
    [123.85, 44.35],
    [124.10, 43.80],
    [124.00, 43.25],
    [123.55, 42.75],
    [122.85, 42.35],
    [122.00, 42.15],
    [121.10, 42.25],
    [120.25, 42.45],
    [119.55, 42.80],
    [119.15, 43.35],
    [119.05, 43.95],
    [119.25, 44.45],
    [119.55, 44.75],  # close
]

# 浑善达克沙地 (Otindag/Hunshandake): elongated E-W, ~21,400 km², Xilingol League.
# Clockwise from NW corner.
OTINDAG_COORDS = [
    [112.10, 43.55],
    [113.00, 43.70],
    [113.85, 43.78],
    [114.80, 43.80],
    [115.60, 43.70],
    [116.30, 43.45],
    [116.85, 43.15],
    [117.10, 42.70],
    [116.75, 42.25],
    [115.90, 42.05],
    [114.95, 42.00],
    [114.05, 42.10],
    [113.20, 42.25],
    [112.45, 42.45],
    [111.95, 42.80],
    [111.85, 43.20],
    [112.10, 43.55],  # close
]

# 三北防护林: rough outer arc across northern China (kept loose as visual frame).
SHELTERBELT_COORDS = [
    [73.0, 35.5],
    [85.0, 36.0],
    [95.0, 37.5],
    [105.0, 37.8],
    [112.0, 39.0],
    [118.0, 41.0],
    [122.0, 43.0],
    [125.5, 46.0],
    [127.0, 49.0],
    [123.0, 50.0],
    [115.0, 49.5],
    [105.0, 48.5],
    [95.0, 47.0],
    [85.0, 46.0],
    [75.0, 44.0],
    [73.0, 40.0],
    [73.0, 35.5],  # close
]


def polygon(coords: list[list[float]]) -> dict:
    return {"type": "Polygon", "coordinates": [coords]}


UPDATES = {
    1: polygon(HORQIN_COORDS),
    2: polygon(OTINDAG_COORDS),
    3: polygon(SHELTERBELT_COORDS),
}


async def main() -> None:
    async with AsyncSessionLocal() as session:
        for region_id, geom in UPDATES.items():
            await session.execute(
                text("UPDATE regions SET bbox_json = :g WHERE id = :i"),
                {"g": json.dumps(geom), "i": region_id},
            )
        await session.commit()

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            text("SELECT id, name, jsonb_array_length(bbox_json->'coordinates'->0) FROM regions ORDER BY id")
        )).fetchall()
        for r in rows:
            print(f"  region {r[0]} {r[1]}: {r[2]} points")


if __name__ == "__main__":
    asyncio.run(main())

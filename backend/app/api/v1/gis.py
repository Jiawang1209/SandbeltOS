import json

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/regions")
async def get_regions(db: AsyncSession = Depends(get_db)):
    """Get all regions with bounding box as GeoJSON features."""
    result = await db.execute(
        text("SELECT id, name, level, area_km2, bbox_json FROM regions ORDER BY id")
    )
    rows = result.fetchall()

    features = []
    for row in rows:
        bbox_raw = row[4]
        geometry = None
        if bbox_raw:
            bbox = json.loads(bbox_raw) if isinstance(bbox_raw, str) else bbox_raw
            if "coordinates" in bbox:
                geometry = {
                    "type": bbox.get("type", "Polygon"),
                    "coordinates": bbox["coordinates"],
                }
            elif all(k in bbox for k in ("north", "south", "east", "west")):
                n, s, e, w = bbox["north"], bbox["south"], bbox["east"], bbox["west"]
                geometry = {
                    "type": "Polygon",
                    "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
                }

        features.append({
            "type": "Feature",
            "properties": {
                "id": row[0],
                "name": row[1],
                "level": row[2],
                "area_km2": float(row[3]) if row[3] else None,
            },
            "geometry": geometry,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }

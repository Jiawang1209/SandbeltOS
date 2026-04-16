from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/regions")
async def get_regions(db: AsyncSession = Depends(get_db)):
    """Get all regions as a list (GeoJSON support added when PostGIS is available)."""
    result = await db.execute(
        text("SELECT id, name, level, area_km2 FROM regions ORDER BY id")
    )
    rows = result.fetchall()

    regions = [
        {
            "id": row[0],
            "name": row[1],
            "level": row[2],
            "area_km2": row[3],
        }
        for row in rows
    ]

    return {"regions": regions}

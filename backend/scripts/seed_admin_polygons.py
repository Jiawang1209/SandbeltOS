"""Replace oval polygons with real administrative banner/county boundaries.

Each sandy land is now represented as a MultiPolygon composed of the banner
(旗/县) boundaries it primarily covers. Data from datav.aliyun.com.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import text

from app.database import async_session as AsyncSessionLocal

ADM_DIR = Path("/tmp/adm")

# 科尔沁沙地 (Horqin) - banners it primarily covers
HORQIN_ADCODES = {
    "150521",  # 科尔沁左翼中旗
    "150522",  # 科尔沁左翼后旗
    "150523",  # 开鲁县
    "150524",  # 库伦旗
    "150525",  # 奈曼旗
    "150421",  # 阿鲁科尔沁旗
    "150424",  # 翁牛特旗
    "150430",  # 敖汉旗
}

# 浑善达克沙地 (Otindag)
OTINDAG_ADCODES = {
    "152502",  # 锡林浩特市
    "152528",  # 镶黄旗
    "152529",  # 正镶白旗
    "152530",  # 正蓝旗
    "152531",  # 多伦县
    "152522",  # 阿巴嘎旗 (southern sliver but include for continuity)
}


def load_features() -> dict[str, dict]:
    features: dict[str, dict] = {}
    for fname in ("tongliao.json", "chifeng.json", "xilingol.json"):
        data = json.loads((ADM_DIR / fname).read_text())
        for ft in data["features"]:
            features[str(ft["properties"]["adcode"])] = ft
    return features


def build_multipolygon(features: dict[str, dict], adcodes: set[str]) -> dict:
    """Combine selected features into a single MultiPolygon geometry."""
    polys: list = []
    for code in adcodes:
        ft = features.get(code)
        if not ft:
            print(f"  WARN missing {code}")
            continue
        geom = ft["geometry"]
        if geom["type"] == "MultiPolygon":
            polys.extend(geom["coordinates"])
        elif geom["type"] == "Polygon":
            polys.append(geom["coordinates"])
    return {"type": "MultiPolygon", "coordinates": polys}


async def main() -> None:
    features = load_features()

    horqin_geom = build_multipolygon(features, HORQIN_ADCODES)
    otindag_geom = build_multipolygon(features, OTINDAG_ADCODES)

    print(f"Horqin: {len(horqin_geom['coordinates'])} polygons")
    print(f"Otindag: {len(otindag_geom['coordinates'])} polygons")

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("UPDATE regions SET bbox_json = :g WHERE id = :i"),
            {"g": json.dumps(horqin_geom), "i": 1},
        )
        await session.execute(
            text("UPDATE regions SET bbox_json = :g WHERE id = :i"),
            {"g": json.dumps(otindag_geom), "i": 2},
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
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
            print(f"  region {r[0]} {r[1]}: {r[2]} with {r[3]} polygons")


if __name__ == "__main__":
    asyncio.run(main())

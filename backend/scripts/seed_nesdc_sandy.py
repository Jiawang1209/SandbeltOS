"""Swap the MODIS-derived sandy-land polygons for official NESDC vectors.

Background
----------
Up until 2026-05-18 the two regions stored a MODIS-derived MultiPolygon
in `regions.bbox_json` (extracted by `extract_sandy_boundary.py` —
NDVI<0.48 growing-season mean, 265/46 polygons). That works for the
demo, but a real ecology audience expects the **official NESDC
vector** for the two sandy lands. This script replaces the geometry
in-place while preserving `area_km2` (which is authoritative — see
project memory `[[project-sandy-land-areas]]`).

Where to get the NESDC file
---------------------------
1. Register at https://www.nesdc.org.cn/
2. Search for "中国沙漠 / 沙地分布图" (China desert / sandy land
   distribution map) — typical product code: 沙地数据 / Lab. of
   Ecosystem Networks.
3. Download the shapefile + reproject to EPSG:4326 (WGS84) if it's
   not already.
4. Extract the two sandy-land features as GeoJSON.
   Example (using `ogr2ogr`):
       ogr2ogr -t_srs EPSG:4326 -where "NAME='科尔沁沙地'" \
           korqin_nesdc.geojson nesdc_sandy_lands.shp
       ogr2ogr -t_srs EPSG:4326 -where "NAME='浑善达克沙地'" \
           hunshandake_nesdc.geojson nesdc_sandy_lands.shp

Usage
-----
    # Dry-run: report what would happen, write nothing.
    python -m scripts.seed_nesdc_sandy \\
        --korqin       /tmp/korqin_nesdc.geojson \\
        --hunshandake  /tmp/hunshandake_nesdc.geojson \\
        --dry-run

    # Real swap (backs up current bbox_json to a dated table first).
    python -m scripts.seed_nesdc_sandy \\
        --korqin       /tmp/korqin_nesdc.geojson \\
        --hunshandake  /tmp/hunshandake_nesdc.geojson

Behaviour
---------
* Each input is a GeoJSON file containing either a Polygon /
  MultiPolygon geometry, or a single-feature FeatureCollection.
* Geometry is normalised to MultiPolygon before writing.
* Pre-swap snapshot is copied to `regions_nesdc_swap_backup_<YYYYMMDD>`
  before any UPDATE.
* `area_km2` is preserved (authoritative); pass `--recompute-area` to
  overwrite it with the planar approximation from the new polygon.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Heavy imports (shapely / sqlalchemy / app.database) are deferred to
# runtime so --help works without the full backend env installed.

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


REGION_KORQIN = 1
REGION_HUNSHANDAKE = 2


def load_geojson_as_multipolygon(path: Path) -> dict[str, Any]:
    """Read a GeoJSON file and return its geometry as a MultiPolygon dict.

    Accepts: bare Polygon, bare MultiPolygon, Feature, or 1-feature
    FeatureCollection. Everything else raises.
    """
    data = json.loads(path.read_text())
    geom: dict[str, Any]
    if data.get("type") == "FeatureCollection":
        feats = data.get("features") or []
        if len(feats) == 0:
            raise ValueError(f"{path}: FeatureCollection has no features")
        if len(feats) > 1:
            raise ValueError(
                f"{path}: FeatureCollection has {len(feats)} features; "
                "pre-split with `ogr2ogr -where` first."
            )
        geom = feats[0]["geometry"]
    elif data.get("type") == "Feature":
        geom = data["geometry"]
    else:
        geom = data

    if geom.get("type") not in {"Polygon", "MultiPolygon"}:
        raise ValueError(
            f"{path}: unsupported geometry type {geom.get('type')!r}; "
            "expected Polygon or MultiPolygon."
        )

    # Normalise to MultiPolygon for consistency with the existing storage.
    if geom["type"] == "Polygon":
        return {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
    return geom


def planar_area_km2(geom: dict[str, Any]) -> float:
    """Rough area (km²) using cos(mean_lat) planar approximation.

    Same formula the project's `seed_accurate_sandy.py` uses; good
    enough for sandy-land scale (off by <2% in this latitude range).
    """
    from shapely.geometry import shape  # noqa: PLC0415 — deferred for --help

    g = shape(geom)
    minx, miny, maxx, maxy = g.bounds
    mean_lat = (miny + maxy) / 2
    km2_per_deg2 = (111.32 ** 2) * math.cos(math.radians(mean_lat))
    return g.area * km2_per_deg2


async def backup_current_geometries(session, backup_table: str) -> None:
    """CREATE TABLE backup AS SELECT … to snapshot before UPDATE."""
    from sqlalchemy import text  # noqa: PLC0415 — deferred for --help

    # Skip if the backup already exists (idempotent re-runs).
    exists = (
        await session.execute(
            text("SELECT to_regclass(:t)"), {"t": backup_table}
        )
    ).scalar()
    if exists is not None:
        print(f"  backup table {backup_table} already exists — skipping snapshot")
        return
    await session.execute(
        text(
            f"CREATE TABLE {backup_table} AS "
            "SELECT id, name, area_km2, bbox_json, NOW() AS backed_up_at "
            "FROM regions WHERE id IN (:k, :h)"
        ),
        {"k": REGION_KORQIN, "h": REGION_HUNSHANDAKE},
    )
    print(f"  snapshot saved to {backup_table}")


async def apply_swap(
    inputs: dict[int, Path],
    recompute_area: bool,
    dry_run: bool,
) -> None:
    from sqlalchemy import text  # noqa: PLC0415 — deferred for --help
    from app.database import async_session  # noqa: PLC0415

    geometries: dict[int, dict[str, Any]] = {}
    for region_id, path in inputs.items():
        geom = load_geojson_as_multipolygon(path)
        n_polys = len(geom["coordinates"])
        approx_area = planar_area_km2(geom)
        print(
            f"  region {region_id} ← {path.name}: "
            f"MultiPolygon with {n_polys} polygons, ~{approx_area:,.0f} km²"
        )
        geometries[region_id] = geom

    if dry_run:
        print("\n[dry-run] no DB writes — re-run without --dry-run to apply.")
        return

    backup_table = f"regions_nesdc_swap_backup_{date.today().strftime('%Y%m%d')}"

    async with async_session() as session:
        await backup_current_geometries(session, backup_table)
        for region_id, geom in geometries.items():
            params = {"g": json.dumps(geom), "i": region_id}
            if recompute_area:
                params["a"] = planar_area_km2(geom)
                stmt = (
                    "UPDATE regions SET bbox_json = :g, area_km2 = :a "
                    "WHERE id = :i"
                )
            else:
                stmt = "UPDATE regions SET bbox_json = :g WHERE id = :i"
            await session.execute(text(stmt), params)
        await session.commit()

    # Verify
    async with async_session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, name, area_km2, bbox_json->>'type' AS t, "
                    "jsonb_array_length(bbox_json->'coordinates') AS n "
                    "FROM regions WHERE id IN (:k, :h) ORDER BY id"
                ),
                {"k": REGION_KORQIN, "h": REGION_HUNSHANDAKE},
            )
        ).fetchall()
        print("\nPost-swap state:")
        for r in rows:
            print(
                f"  region {r[0]} {r[1]}: {r[2]:,.0f} km² — {r[3]} "
                f"with {r[4]} polygons"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--korqin",
        type=Path,
        required=True,
        help="GeoJSON file for the Korqin (科尔沁) sandy land.",
    )
    parser.add_argument(
        "--hunshandake",
        type=Path,
        required=True,
        help="GeoJSON file for the Hunshandake (浑善达克) sandy land.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would happen; write nothing to the DB.",
    )
    parser.add_argument(
        "--recompute-area",
        action="store_true",
        help=(
            "Also overwrite area_km2 with a planar approximation. "
            "Default = keep existing area_km2 (authoritative)."
        ),
    )
    args = parser.parse_args()

    for path in (args.korqin, args.hunshandake):
        if not path.exists():
            print(f"error: {path} does not exist", file=sys.stderr)
            return 1

    inputs = {
        REGION_KORQIN: args.korqin,
        REGION_HUNSHANDAKE: args.hunshandake,
    }
    print(
        f"NESDC sandy-land swap — dry_run={args.dry_run}, "
        f"recompute_area={args.recompute_area}\n"
    )
    asyncio.run(apply_swap(inputs, args.recompute_area, args.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())

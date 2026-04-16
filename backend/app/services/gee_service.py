from __future__ import annotations

import pandas as pd


def _get_ee():
    """Lazy import of earthengine-api."""
    import ee
    return ee


def init_gee(service_account: str = "", key_file: str = "") -> None:
    """Initialize GEE. Uses service account if provided, otherwise default credentials."""
    ee = _get_ee()
    try:
        if service_account and key_file:
            credentials = ee.ServiceAccountCredentials(service_account, key_file)
            ee.Initialize(credentials)
        else:
            ee.Initialize()
    except ee.EEException:
        ee.Authenticate()
        ee.Initialize()


def fetch_modis_ndvi(
    region_geom: dict,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Fetch MODIS MOD13A1 16-day NDVI from GEE.

    Args:
        region_geom: GeoJSON geometry dict
        start_date: 'YYYY-MM-DD'
        end_date: 'YYYY-MM-DD'

    Returns:
        DataFrame with columns: time, ndvi_mean, ndvi_min, ndvi_max, evi_mean
    """
    ee = _get_ee()
    roi = ee.Geometry(region_geom)

    collection = (
        ee.ImageCollection("MODIS/061/MOD13A1")
        .filterDate(start_date, end_date)
        .filterBounds(roi)
        .select(["NDVI", "EVI"])
    )

    def extract_stats(image: ee.Image) -> ee.Feature:
        date = image.date().format("YYYY-MM-dd")
        ndvi = image.select("NDVI").multiply(0.0001)
        evi = image.select("EVI").multiply(0.0001)

        ndvi_stats = ndvi.reduceRegion(
            reducer=ee.Reducer.mean()
            .combine(ee.Reducer.min(), sharedInputs=True)
            .combine(ee.Reducer.max(), sharedInputs=True),
            geometry=roi,
            scale=500,
            maxPixels=1e13,
        )
        evi_stats = evi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=500,
            maxPixels=1e13,
        )
        return ee.Feature(
            None,
            ndvi_stats.combine(evi_stats).set("date", date),
        )

    features = collection.map(extract_stats)
    result = features.getInfo()

    rows = []
    for feat in result["features"]:
        p = feat["properties"]
        rows.append(
            {
                "time": p["date"],
                "ndvi_mean": p.get("NDVI_mean"),
                "ndvi_min": p.get("NDVI_min"),
                "ndvi_max": p.get("NDVI_max"),
                "evi_mean": p.get("EVI_mean"),
            }
        )
    return pd.DataFrame(rows)


def fetch_modis_lst(
    region_geom: dict,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch MOD11A2 land surface temperature (8-day composite)."""
    ee = _get_ee()
    roi = ee.Geometry(region_geom)

    collection = (
        ee.ImageCollection("MODIS/061/MOD11A2")
        .filterDate(start_date, end_date)
        .filterBounds(roi)
        .select(["LST_Day_1km"])
    )

    def extract(image: ee.Image) -> ee.Feature:
        lst_c = image.select("LST_Day_1km").multiply(0.02).subtract(273.15)
        stats = lst_c.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=1000,
            maxPixels=1e13,
        )
        return ee.Feature(
            None, stats.set("date", image.date().format("YYYY-MM-dd"))
        )

    result = collection.map(extract).getInfo()
    rows = [
        {
            "time": f["properties"]["date"],
            "lst_mean": f["properties"].get("LST_Day_1km"),
        }
        for f in result["features"]
    ]
    return pd.DataFrame(rows)


def fetch_smap_soil_moisture(
    region_geom: dict,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch SMAP L4 surface soil moisture (daily)."""
    ee = _get_ee()
    roi = ee.Geometry(region_geom)

    collection = (
        ee.ImageCollection("NASA/SMAP/SPL4SMGP/007")
        .filterDate(start_date, end_date)
        .filterBounds(roi)
        .select(["sm_surface"])
    )

    def extract(image: ee.Image) -> ee.Feature:
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=11000,
            maxPixels=1e13,
        )
        return ee.Feature(
            None, stats.set("date", image.date().format("YYYY-MM-dd"))
        )

    result = collection.map(extract).getInfo()
    rows = [
        {
            "time": f["properties"]["date"],
            "soil_moisture": f["properties"].get("sm_surface"),
        }
        for f in result["features"]
    ]
    return pd.DataFrame(rows)


# === Horqin Sandy Land bounding geometry (simplified) ===
HORQIN_GEOJSON = {
    "type": "Polygon",
    "coordinates": [
        [
            [119.0, 42.0],
            [124.0, 42.0],
            [124.0, 45.0],
            [119.0, 45.0],
            [119.0, 42.0],
        ]
    ],
}

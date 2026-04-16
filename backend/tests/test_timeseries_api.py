"""Integration tests for the ecological timeseries API endpoint.

These tests run against the real database (requires seeded data).
"""

import pytest


@pytest.mark.asyncio
async def test_timeseries_returns_ndvi_data(client):
    response = await client.get(
        "/api/v1/ecological/timeseries",
        params={"region_id": 1, "indicator": "ndvi"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["indicator"] == "ndvi"
    assert data["region"]["name"] == "科尔沁沙地"
    assert len(data["data"]) > 0
    assert "time" in data["data"][0]
    assert "value" in data["data"][0]


@pytest.mark.asyncio
async def test_timeseries_returns_evi_data(client):
    response = await client.get(
        "/api/v1/ecological/timeseries",
        params={"region_id": 1, "indicator": "evi"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["indicator"] == "evi"
    assert len(data["data"]) > 0


@pytest.mark.asyncio
async def test_timeseries_date_filtering(client):
    response = await client.get(
        "/api/v1/ecological/timeseries",
        params={
            "region_id": 1,
            "indicator": "ndvi",
            "start_date": "2023-06-01",
            "end_date": "2023-09-01",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) > 0
    for record in data["data"]:
        assert record["time"] >= "2023-06-01"
        assert record["time"] <= "2023-09-02"  # allow for timezone


@pytest.mark.asyncio
async def test_timeseries_nonexistent_region(client):
    response = await client.get(
        "/api/v1/ecological/timeseries",
        params={"region_id": 9999, "indicator": "ndvi"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_timeseries_empty_indicator(client):
    response = await client.get(
        "/api/v1/ecological/timeseries",
        params={"region_id": 1, "indicator": "nonexistent"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_regions_endpoint(client):
    response = await client.get("/api/v1/gis/regions")

    assert response.status_code == 200
    data = response.json()
    assert len(data["regions"]) > 0
    assert data["regions"][0]["name"] == "科尔沁沙地"

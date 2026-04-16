const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Region {
  id: number;
  name: string;
  level: string;
  area_km2: number | null;
}

export interface RegionFeature {
  type: "Feature";
  properties: Region;
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  } | null;
}

export interface RegionsGeoJSON {
  type: "FeatureCollection";
  features: RegionFeature[];
}

export interface TimeseriesRecord {
  time: string;
  value: number;
  source: string;
}

export interface TimeseriesResponse {
  region: Region;
  indicator: string;
  data: TimeseriesRecord[];
}

export interface WeatherRecord {
  time: string;
  precipitation: number;
  temperature: number;
  wind_speed: number;
  wind_direction: number;
  evapotranspiration: number;
  soil_moisture: number;
}

export interface WeatherResponse {
  region_id: number;
  data: WeatherRecord[];
}

export async function fetchRegions(): Promise<RegionsGeoJSON> {
  const res = await fetch(`${API_BASE}/api/v1/gis/regions`);
  return res.json();
}

export async function fetchTimeseries(
  regionId: number,
  indicator: string,
  startDate = "2020-01-01",
  endDate = "2024-12-31"
): Promise<TimeseriesResponse> {
  const params = new URLSearchParams({
    region_id: String(regionId),
    indicator,
    start_date: startDate,
    end_date: endDate,
  });
  const res = await fetch(`${API_BASE}/api/v1/ecological/timeseries?${params}`);
  return res.json();
}

export async function fetchWeather(
  regionId: number,
  startDate = "2020-01-01",
  endDate = "2024-12-31"
): Promise<WeatherResponse> {
  const params = new URLSearchParams({
    region_id: String(regionId),
    start_date: startDate,
    end_date: endDate,
  });
  const res = await fetch(`${API_BASE}/api/v1/ecological/weather?${params}`);
  return res.json();
}

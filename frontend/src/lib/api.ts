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
  startDate = "2015-01-01",
  endDate = "2025-12-31"
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
  startDate = "2015-01-01",
  endDate = "2025-12-31"
): Promise<WeatherResponse> {
  const params = new URLSearchParams({
    region_id: String(regionId),
    start_date: startDate,
    end_date: endDate,
  });
  const res = await fetch(`${API_BASE}/api/v1/ecological/weather?${params}`);
  return res.json();
}

// ---------------- Phase 3: risk + alerts ----------------

export interface RiskFactors {
  fvc?: number;
  ndvi?: number;
  wind_speed?: number;
  wind_erosion?: number;
  soil_moisture?: number | null;
  lst?: number | null;
  thermal?: number;
  carbon_density?: number;
}

export interface RiskRecord {
  time: string;
  risk_level: number; // 1..4
  risk_score: number;
  wind_erosion_modulus: number;
  sand_fixation_amount: number;
  factors: RiskFactors;
}

export interface AlertRecord {
  id: number;
  created_at: string;
  region_id?: number;
  region_name?: string;
  alert_type: string;
  severity: "high" | "critical" | string;
  message: string;
}

export interface CurrentStatusResponse {
  region: Region;
  latest: RiskRecord | null;
  alerts: AlertRecord[];
}

export interface RiskTimeseriesResponse {
  region_id: number;
  data: RiskRecord[];
}

export async function fetchCurrentStatus(
  regionId: number
): Promise<CurrentStatusResponse> {
  const res = await fetch(
    `${API_BASE}/api/v1/ecological/current-status?region_id=${regionId}`
  );
  return res.json();
}

export async function fetchRiskTimeseries(
  regionId: number,
  startDate = "2015-01-01",
  endDate = "2025-12-31"
): Promise<RiskTimeseriesResponse> {
  const params = new URLSearchParams({
    region_id: String(regionId),
    start_date: startDate,
    end_date: endDate,
  });
  const res = await fetch(
    `${API_BASE}/api/v1/ecological/risk-timeseries?${params}`
  );
  return res.json();
}

export async function fetchAlerts(
  regionId?: number,
  limit = 20
): Promise<{ data: AlertRecord[] }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (regionId != null) params.set("region_id", String(regionId));
  const res = await fetch(`${API_BASE}/api/v1/ecological/alerts?${params}`);
  return res.json();
}

// ---------------- Pixel-grid NDVI hotspots ----------------

export interface GridCellFeature {
  type: "Feature";
  properties: { col: number; row: number; ndvi: number };
  geometry: { type: "Polygon"; coordinates: number[][][] };
}

export interface GridGeoJSON {
  type: "FeatureCollection";
  features: GridCellFeature[];
}

export async function fetchNdviGrid(
  regionId: number,
  year: number
): Promise<GridGeoJSON> {
  const res = await fetch(
    `${API_BASE}/api/v1/grid/ndvi/${regionId}?year=${year}`
  );
  if (!res.ok) {
    return { type: "FeatureCollection", features: [] };
  }
  return res.json();
}

export async function fetchNdviGridYears(regionId: number): Promise<number[]> {
  const res = await fetch(`${API_BASE}/api/v1/grid/ndvi/${regionId}/years`);
  if (!res.ok) return [];
  const body = await res.json();
  return body.years ?? [];
}

// ---------------- Land-cover composition ----------------

export interface LandCoverYear {
  year: number;
  barren: number;
  grass: number;
  shrub: number;
  crop: number;
  forest: number;
  other: number;
}

export interface LandCoverResponse {
  region: Region;
  series: LandCoverYear[];
}

export async function fetchLandCover(
  regionId: number
): Promise<LandCoverResponse> {
  const res = await fetch(
    `${API_BASE}/api/v1/ecological/landcover?region_id=${regionId}`
  );
  if (!res.ok) {
    throw new Error(`landcover fetch failed (${res.status})`);
  }
  return res.json();
}

// ---------------- Landsat true-color basemap ----------------

export interface LandsatTileResponse {
  year: number;
  collection: string;
  tile_url: string;
  attribution: string;
}

export async function fetchLandsatTileUrl(
  year: number
): Promise<LandsatTileResponse> {
  const res = await fetch(`${API_BASE}/api/v1/basemap/landsat?year=${year}`);
  if (!res.ok) {
    throw new Error(`Landsat tile fetch failed (${res.status})`);
  }
  return res.json();
}

export const RISK_LEVEL_LABELS: Record<number, string> = {
  1: "低风险",
  2: "中等风险",
  3: "高风险",
  4: "极高风险",
};

export const RISK_LEVEL_COLORS: Record<number, string> = {
  1: "#16a34a", // green
  2: "#eab308", // yellow
  3: "#f97316", // orange
  4: "#dc2626", // red
};

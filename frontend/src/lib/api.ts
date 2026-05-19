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

export type GridSource = "modis" | "s2";

export async function fetchNdviGrid(
  regionId: number,
  year: number,
  source: GridSource = "modis",
): Promise<GridGeoJSON> {
  const params = new URLSearchParams({ year: String(year), source });
  const res = await fetch(
    `${API_BASE}/api/v1/grid/ndvi/${regionId}?${params}`,
  );
  if (!res.ok) {
    return { type: "FeatureCollection", features: [] };
  }
  return res.json();
}

export async function fetchNdviGridYears(
  regionId: number,
  source: GridSource = "modis",
): Promise<number[]> {
  const res = await fetch(
    `${API_BASE}/api/v1/grid/ndvi/${regionId}/years?source=${source}`,
  );
  if (!res.ok) return [];
  const body = await res.json();
  return body.years ?? [];
}

// ---------------- NDVI diff (change detection) ----------------

export interface NdviDiffCell {
  col: number;
  row: number;
  ndvi_before: number;
  ndvi_after: number;
  diff: number;
}

export interface NdviDiffSummary {
  region_id: number;
  before_year: number;
  after_year: number;
  n_cells: number;
  mean_diff: number;
  gain_cells: number;
  loss_cells: number;
  top_gain: NdviDiffCell[];
  top_loss: NdviDiffCell[];
}

export interface NdviDiffResponse {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    properties: NdviDiffCell;
    geometry: { type: "Polygon"; coordinates: number[][][] };
  }>;
  summary: NdviDiffSummary;
}

export async function fetchNdviDiff(
  regionId: number,
  beforeYear: number,
  afterYear: number,
  source: GridSource = "modis",
): Promise<NdviDiffResponse | null> {
  const params = new URLSearchParams({
    before: String(beforeYear),
    after: String(afterYear),
    source,
  });
  const res = await fetch(
    `${API_BASE}/api/v1/grid/ndvi-diff/${regionId}?${params}`,
  );
  if (!res.ok) return null;
  return res.json();
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

// ---------------- Phase 5: prediction + scenario ----------------

export interface ForecastPoint {
  date: string;
  yhat: number;
  yhat_lower: number;
  yhat_upper: number;
}

export interface ForecastResponse {
  region_id: number;
  indicator: string;
  model: "prophet";
  fitted_on_n_points: number;
  history_end: string;
  horizon_steps: number;
  freq: string;
  points: ForecastPoint[];
}

export async function fetchNdviForecast(
  regionId: number,
  horizon: number = 12
): Promise<ForecastResponse | null> {
  const params = new URLSearchParams({
    region_id: String(regionId),
    horizon: String(horizon),
  });
  const res = await fetch(
    `${API_BASE}/api/v1/prediction/ndvi-forecast?${params}`
  );
  if (!res.ok) return null;
  return res.json();
}

// Six species keys must stay in sync with backend `Species` literal.
export type ScenarioSpecies =
  | "poplar"
  | "willow"
  | "pine"
  | "elm"
  | "seabuckthorn"
  | "caragana";

export interface SpeciesOption {
  key: ScenarioSpecies;
  label_cn: string;
  water_use_mm: number;
}

export interface ScenarioBaseline {
  current_fvc: number;
  current_soil_moisture: number;
  annual_precip_mm: number;
  avg_wind_speed_ms: number;
}

export interface ScenarioDefaultsResponse {
  region_id: number;
  baseline: ScenarioBaseline;
  species_options: SpeciesOption[];
}

export interface YearlyProjection {
  year: number;
  fvc: number;
  soil_moisture: number;
  water_deficit_mm: number;
  wind_erosion: number;
  risk_level: number;
  risk_label: string;
  risk_score: number;
  warning: string | null;
}

export interface ScenarioRequest {
  region_id: number;
  species: ScenarioSpecies;
  additional_density_per_ha: number;
  years: number;
  // Optional overrides; omit to let server fill from regional baseline.
  current_fvc?: number;
  current_soil_moisture?: number;
  annual_precip_mm?: number;
  avg_wind_speed_ms?: number;
}

export interface ScenarioResponse {
  region_id: number;
  species: ScenarioSpecies;
  species_label: string;
  additional_density_per_ha: number;
  years: number;
  baseline_used: ScenarioBaseline;
  yearly: YearlyProjection[];
  recommendation: string;
}

export async function fetchScenarioDefaults(
  regionId: number
): Promise<ScenarioDefaultsResponse | null> {
  const res = await fetch(
    `${API_BASE}/api/v1/prediction/scenario-defaults?region_id=${regionId}`
  );
  if (!res.ok) return null;
  return res.json();
}

export async function postScenario(
  req: ScenarioRequest
): Promise<ScenarioResponse | null> {
  const res = await fetch(`${API_BASE}/api/v1/prediction/scenario`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) return null;
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

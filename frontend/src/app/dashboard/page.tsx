"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import RegionMap, { type MapLayerMode } from "@/components/RegionMap";

// Chat widget loads client-side only — it uses fetch streaming + portals that
// don't SSR cleanly, and keeping it off the critical path preserves dashboard LCP.
const ChatWidget = dynamic(
  () => import("@/components/ChatWidget").then((m) => m.ChatWidget),
  { ssr: false },
);

// Map dashboard region id (regions.id from DB) to the RAG-level alias the chat
// endpoint expects. Kept here (not in live_metrics) because the dashboard owns
// the selection state and shouldn't leak DB ids across the wire.
const REGION_ID_TO_ALIAS: Record<number, string> = {
  1: "horqin",
  2: "hunshandake",
};
import SwipeCompareMap from "@/components/SwipeCompareMap";
import NdviChart from "@/components/NdviChart";
import WeatherChart from "@/components/WeatherChart";
import RiskChart from "@/components/RiskChart";
import AlertBanner from "@/components/AlertBanner";
import AchievementChart from "@/components/AchievementChart";
import ComparisonChart from "@/components/ComparisonChart";
import LandCoverChart from "@/components/LandCoverChart";
import TimeSlider from "@/components/TimeSlider";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";
import StatsBar from "@/components/StatsBar";
import {
  fetchRegions,
  fetchTimeseries,
  fetchWeather,
  fetchCurrentStatus,
  fetchRiskTimeseries,
  fetchNdviGrid,
  fetchNdviGridYears,
  fetchLandCover,
  RISK_LEVEL_COLORS,
  RISK_LEVEL_LABELS,
  type RegionsGeoJSON,
  type TimeseriesRecord,
  type WeatherRecord,
  type Region,
  type RiskRecord,
  type AlertRecord,
  type GridGeoJSON,
  type LandCoverYear,
} from "@/lib/api";

interface RegionData {
  region: Region;
  ndvi: TimeseriesRecord[];
  evi: TimeseriesRecord[];
  weather: WeatherRecord[];
  risk: RiskRecord[];
  latest: RiskRecord | null;
  alerts: AlertRecord[];
}

export default function DashboardPage() {
  const [regions, setRegions] = useState<RegionsGeoJSON | null>(null);
  const [regionDataMap, setRegionDataMap] = useState<Record<number, RegionData>>({});
  // selectedId === null means the "两大沙地" combined view. A numeric id narrows
  // the entire dashboard to that single sandy land.
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [ndviSummary, setNdviSummary] = useState<Record<number, number>>({});
  const [riskSummary, setRiskSummary] = useState<Record<number, number>>({});
  const [layerMode, setLayerMode] = useState<MapLayerMode>("ndvi");
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [hotspotGrid, setHotspotGrid] = useState<GridGeoJSON | null>(null);
  const [hotspotYears, setHotspotYears] = useState<number[]>([]);
  // Compare mode replaces the map with a Landsat true-color swipe view.
  const [compareMode, setCompareMode] = useState(false);
  const [compareBeforeYear, setCompareBeforeYear] = useState(2015);
  const [compareAfterYear, setCompareAfterYear] = useState(2024);
  // Land-cover composition keyed by region id. Lazy-fetched per sandy land.
  const [landCover, setLandCover] = useState<Record<number, LandCoverYear[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // year -> regionId -> yearly NDVI mean
  const ndviByYear = useMemo(() => {
    const out: Record<number, Record<number, number>> = {};
    for (const [idStr, rd] of Object.entries(regionDataMap)) {
      const id = Number(idStr);
      const buckets = new Map<number, number[]>();
      for (const d of rd.ndvi) {
        const y = new Date(d.time).getUTCFullYear();
        if (!Number.isFinite(y) || !Number.isFinite(d.value)) continue;
        const arr = buckets.get(y) ?? buckets.set(y, []).get(y)!;
        arr.push(d.value);
      }
      for (const [year, vs] of buckets) {
        if (!out[year]) out[year] = {};
        out[year][id] = vs.reduce((s, v) => s + v, 0) / vs.length;
      }
    }
    return out;
  }, [regionDataMap]);

  const availableYears = useMemo(
    () => Object.keys(ndviByYear).map(Number).sort((a, b) => a - b),
    [ndviByYear]
  );

  // Initialize the year at the earliest available so the dashboard tells the
  // restoration story forward in time. The user drives "play" from the
  // starting point.
  useEffect(() => {
    if (selectedYear == null && availableYears.length > 0) {
      setSelectedYear(availableYears[0]);
    }
  }, [availableYears, selectedYear]);

  // Reset the time slider to the earliest year whenever the selected region
  // changes, so switching sandy lands or returning to the overview always
  // restarts the restoration story from the beginning.
  useEffect(() => {
    if (availableYears.length === 0) return;
    setSelectedYear(availableYears[0]);
  }, [selectedId, availableYears]);

  // Discover which years have cached hotspot grids for the selected region,
  // so the time slider can snap to the nearest available year in hotspot mode.
  useEffect(() => {
    if (selectedId == null) return;
    let cancelled = false;
    fetchNdviGridYears(selectedId).then((ys) => {
      if (!cancelled) setHotspotYears(ys);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  // Fetch land-cover composition the first time a sandy land is selected.
  // Cached in-memory by region id so repeat visits avoid the roundtrip.
  useEffect(() => {
    if (selectedId == null || landCover[selectedId] != null) return;
    let cancelled = false;
    fetchLandCover(selectedId)
      .then((res) => {
        if (!cancelled) {
          setLandCover((prev) => ({ ...prev, [selectedId]: res.series }));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLandCover((prev) => ({ ...prev, [selectedId]: [] }));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, landCover]);

  // Fetch the grid for (region, year) when hotspot mode is active. Snaps to
  // the nearest cached year since we only pre-computed a sparse set.
  useEffect(() => {
    if (layerMode !== "hotspot" || selectedId == null || selectedYear == null) {
      setHotspotGrid(null);
      return;
    }
    if (hotspotYears.length === 0) return;
    const nearest = hotspotYears.reduce((best, y) =>
      Math.abs(y - selectedYear) < Math.abs(best - selectedYear) ? y : best
    );
    let cancelled = false;
    fetchNdviGrid(selectedId, nearest).then((g) => {
      if (!cancelled) setHotspotGrid(g);
    });
    return () => {
      cancelled = true;
    };
  }, [layerMode, selectedId, selectedYear, hotspotYears]);

  useEffect(() => {
    async function load() {
      try {
        const regionsRes = await fetchRegions();
        setRegions(regionsRes);

        const subregions = regionsRes.features.filter(
          (f) => f.properties.level === "subregion"
        );

        const dataMap: Record<number, RegionData> = {};
        const ndviSum: Record<number, number> = {};
        const riskSum: Record<number, number> = {};

        await Promise.all(
          subregions.map(async (f) => {
            const id = f.properties.id;
            const [ndviRes, eviRes, weatherRes, riskRes, statusRes] =
              await Promise.all([
                fetchTimeseries(id, "ndvi"),
                fetchTimeseries(id, "evi"),
                fetchWeather(id),
                fetchRiskTimeseries(id),
                fetchCurrentStatus(id),
              ]);
            dataMap[id] = {
              region: ndviRes.region,
              ndvi: ndviRes.data,
              evi: eviRes.data,
              weather: weatherRes.data,
              risk: riskRes.data,
              latest: statusRes.latest,
              alerts: statusRes.alerts,
            };
            ndviSum[id] =
              ndviRes.data.length > 0
                ? ndviRes.data.reduce((s, d) => s + d.value, 0) /
                  ndviRes.data.length
                : 0;
            riskSum[id] = statusRes.latest?.risk_level ?? 0;
          })
        );

        setRegionDataMap(dataMap);
        setNdviSummary(ndviSum);
        setRiskSummary(riskSum);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleSelectRegion = useCallback((id: number) => {
    // Clicking a polygon on the map drills into that single sandy land.
    setSelectedId(id);
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: "var(--background)" }}>
        <div className="text-sm tracking-wide text-zinc-500">加载数据中…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: "var(--background)" }}>
        <div className="text-sm text-red-600">加载失败: {error}</div>
      </div>
    );
  }

  const current = selectedId != null ? regionDataMap[selectedId] ?? null : null;
  const subregionIds = Object.keys(regionDataMap).map(Number);
  // Aggregate alerts across both sandy lands when in the combined view, so the
  // overview still surfaces anything actionable.
  const currentAlerts = current
    ? current.alerts
    : Object.values(regionDataMap).flatMap((r) => r.alerts);

  // Bundle both sandy-land regions for the side-by-side comparison chart.
  const comparisonBundles = subregionIds
    .map((id) => regionDataMap[id])
    .filter(Boolean)
    .map((rd) => ({ region: rd.region, ndvi: rd.ndvi, risk: rd.risk }));
  const totalArea = comparisonBundles.reduce(
    (s, r) => s + (r.region.area_km2 ?? 0),
    0
  );

  const ndviMean =
    current && current.ndvi.length > 0
      ? current.ndvi.reduce((s, d) => s + d.value, 0) / current.ndvi.length
      : null;
  const fvcPct =
    current?.latest?.factors.fvc != null
      ? current.latest.factors.fvc * 100
      : null;
  const carbon =
    current?.latest?.factors.carbon_density != null
      ? Math.round(current.latest.factors.carbon_density)
      : null;

  return (
    <div className="flex min-h-screen flex-col" style={{ background: "var(--background)" }}>
      {/* Institutional header */}
      <SiteHeader
        regions={[
          { id: null, label: "两大沙地" },
          ...subregionIds.map((id) => ({ id, label: regionDataMap[id].region.name })),
        ]}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />

      {/* Hero stats strip */}
      <StatsBar
        regionCount={subregionIds.length}
        totalAreaKm2={Math.round(totalArea)}
        yearsSpan={
          availableYears.length > 0
            ? { from: availableYears[0], to: availableYears[availableYears.length - 1] }
            : null
        }
        latestRiskLevel={
          current?.latest?.risk_level ??
          (() => {
            const vals = Object.values(regionDataMap)
              .map((r) => r.latest?.risk_level)
              .filter((v): v is number => v != null);
            return vals.length > 0 ? Math.max(...vals) : null;
          })()
        }
        datasetsCount={4}
      />

      {currentAlerts.length > 0 && <AlertBanner alerts={currentAlerts} />}

      <main className="mx-auto w-full max-w-[1600px] flex-1 px-6 py-6">
        <div
          className="grid gap-3"
          style={{
            gridTemplateColumns: "repeat(12, minmax(0, 1fr))",
            gridAutoRows: "minmax(88px, auto)",
          }}
        >
          {current ? (
            <>
              {/* Region hero — single sandy land */}
              <section
                key="hero-region"
                className="card-surface card-surface--warm relative overflow-hidden px-5 py-4"
                style={{ gridColumn: "span 6 / span 6" }}
              >
                <div className="flex h-full items-end justify-between gap-4">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.22em] text-[var(--ink-soft)]">
                      当前监测区
                    </div>
                    <h1 className="mt-1 text-[28px] font-semibold tracking-tight text-[var(--ink)]">
                      {current.region.name}
                    </h1>
                  </div>
                  <div className="flex flex-col items-end gap-1 text-right">
                    <span className="rounded-full bg-[var(--ink)] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em] text-white">
                      {current.region.level}
                    </span>
                    <div className="num text-sm text-[var(--ink-muted)]">
                      {current.region.area_km2?.toLocaleString()}{" "}
                      <span className="text-[var(--ink-soft)]">km²</span>
                    </div>
                  </div>
                </div>
                <div
                  aria-hidden
                  className="pointer-events-none absolute -right-12 -top-10 h-40 w-40 rounded-full opacity-40"
                  style={{
                    background:
                      "radial-gradient(closest-side, rgba(201,164,107,0.35), transparent)",
                  }}
                />
              </section>

              {/* Risk hero */}
              <RiskHero key="hero-risk" latest={current.latest} style={{ gridColumn: "span 6 / span 6" }} />
            </>
          ) : (
            /* Combined overview hero spanning full width */
            <section
              key="hero-overview"
              className="card-surface card-surface--warm relative overflow-hidden px-5 py-4"
              style={{ gridColumn: "span 12 / span 12" }}
            >
              <div className="flex items-end justify-between gap-4">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.22em] text-[var(--ink-soft)]">
                    两大沙地 · 综合视角
                  </div>
                  <h1 className="mt-1 text-[28px] font-semibold tracking-tight text-[var(--ink)]">
                    科尔沁 &amp; 浑善达克
                  </h1>
                  <p className="mt-1 text-[11px] text-[var(--ink-muted)]">
                    点击任一沙地进入单区详情视图
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1 text-right">
                  <span className="rounded-full bg-[var(--ink)] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em] text-white">
                    COMBINED
                  </span>
                  <div className="num text-sm text-[var(--ink-muted)]">
                    {totalArea.toLocaleString()}{" "}
                    <span className="text-[var(--ink-soft)]">km²</span>
                  </div>
                </div>
              </div>
              <div
                aria-hidden
                className="pointer-events-none absolute -right-12 -top-10 h-40 w-40 rounded-full opacity-40"
                style={{
                  background:
                    "radial-gradient(closest-side, rgba(201,164,107,0.35), transparent)",
                }}
              />
            </section>
          )}

          {/* Map — spans 2 rows in single view (alongside KPIs), half-width in
              overview (paired with the project-info panel). Stable `key` keeps the
              MapLibre instance alive when the hero slot above flips between one and
              two children. */}
          <section
            key="map-section"
            className="card-surface relative overflow-hidden"
            style={
              current
                ? { gridColumn: "span 6 / span 6", gridRow: "span 2 / span 2", minHeight: 440 }
                : { gridColumn: "span 6 / span 6", minHeight: 480 }
            }
          >
            {compareMode && current ? (
              <SwipeCompareMap
                regions={regions}
                selectedRegionId={selectedId}
                beforeYear={compareBeforeYear}
                afterYear={compareAfterYear}
              />
            ) : (
              <RegionMap
                regions={regions}
                ndviSummary={ndviSummary}
                riskSummary={riskSummary}
                layerMode={layerMode}
                selectedRegionId={selectedId}
                onSelectRegion={handleSelectRegion}
                ndviYearly={
                  layerMode === "ndvi" && selectedYear != null
                    ? ndviByYear[selectedYear]
                    : undefined
                }
                hotspotGrid={layerMode === "hotspot" ? hotspotGrid : null}
              />
            )}
            {!compareMode && <LayerToggle layerMode={layerMode} onChange={setLayerMode} />}
            {current && (
              <CompareToggle
                enabled={compareMode}
                onToggle={() => setCompareMode((v) => !v)}
              />
            )}
            {compareMode && current && (
              <CompareYearControls
                beforeYear={compareBeforeYear}
                afterYear={compareAfterYear}
                onBeforeChange={setCompareBeforeYear}
                onAfterChange={setCompareAfterYear}
              />
            )}
            {!compareMode && layerMode === "risk" && <RiskLegend />}
            {!compareMode && layerMode === "ndvi" && (
              <NdviGradientLegend title="植被覆盖 NDVI" />
            )}
            {!compareMode && layerMode === "hotspot" && (
              <NdviGradientLegend title="像素 NDVI" />
            )}
            {!compareMode &&
              (layerMode === "ndvi" || layerMode === "hotspot") &&
              selectedYear != null &&
              availableYears.length > 1 && (
                <TimeSlider
                  years={availableYears}
                  value={selectedYear}
                  onChange={setSelectedYear}
                  summary={
                    current && ndviByYear[selectedYear]?.[current.region.id] != null
                      ? `NDVI ${ndviByYear[selectedYear][current.region.id].toFixed(3)}`
                      : undefined
                  }
                />
              )}
          </section>

          {/* Overview info panel — paired with the map to fill the top row with
              project context instead of a single oversized map. */}
          {!current && (
            <ProjectInfoPanel style={{ gridColumn: "span 6 / span 6", minHeight: 480 }} />
          )}

          {current ? (
            <>
              {/* KPI row (right side, first sub-row) */}
              <KpiCard
                label="NDVI 均值"
                value={ndviMean != null ? ndviMean.toFixed(3) : "—"}
                hint="2020-2024"
                tone="moss"
                style={{ gridColumn: "span 2 / span 2" }}
              />
              <KpiCard
                label="植被覆盖度 FVC"
                value={fvcPct != null ? `${fvcPct.toFixed(1)}%` : "—"}
                hint="最新月"
                tone="moss"
                style={{ gridColumn: "span 2 / span 2" }}
              />
              <KpiCard
                label="碳密度"
                value={carbon != null ? carbon.toLocaleString() : "—"}
                hint="gC/m²"
                tone="sand"
                style={{ gridColumn: "span 2 / span 2" }}
              />

              {/* Risk trend chart (right side, second sub-row) */}
              <section
                className="card-surface p-2"
                style={{ gridColumn: "span 6 / span 6", minHeight: 240 }}
              >
                <RiskChart data={current.risk} />
              </section>

              {/* Achievement chart — long-term recovery narrative (moved above NDVI
                  so it animates alongside the map's time slider) */}
              <section
                className="card-surface p-2"
                style={{ gridColumn: "span 6 / span 6", minHeight: 240 }}
              >
                <AchievementChart
                  ndvi={current.ndvi}
                  risk={current.risk}
                  activeYear={selectedYear}
                />
              </section>

              {/* Achievement narrative side panel */}
              <section
                className="card-surface card-surface--warm px-5 py-4"
                style={{ gridColumn: "span 6 / span 6", minHeight: 240 }}
              >
                <div className="text-[10px] uppercase tracking-[0.22em] text-[var(--ink-soft)]">
                  治沙成效说明
                </div>
                <h3 className="mt-1 text-[18px] font-semibold tracking-tight text-[var(--ink)]">
                  三北防护林 · 综合治理
                </h3>
                <p className="mt-2 text-[12px] leading-relaxed text-[var(--ink-muted)]">
                  持续的防护林建设、退耕还林还草和沙化土地封禁保护，在近十年间推动
                  植被指数稳步回升，沙化风险整体下行。
                </p>
                <ul className="mt-4 space-y-2 text-[12px] text-[var(--ink-muted)]">
                  <li className="flex items-start gap-2">
                    <span className="mt-1 inline-block h-2 w-2 rounded-full" style={{ backgroundColor: "#166534" }} />
                    <span>植被年均 NDVI 稳步抬升，生态基底持续改善</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-1 inline-block h-2 w-2 rounded-full" style={{ backgroundColor: "#b91c1c" }} />
                    <span>综合沙化风险得分逐年回落，脆弱性下降</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-1 inline-block h-2 w-2 rounded-full" style={{ backgroundColor: "#a8a29e" }} />
                    <span>监测覆盖科尔沁 / 浑善达克两大重点沙地</span>
                  </li>
                </ul>
              </section>

              {/* NDVI/EVI chart */}
              <section
                className="card-surface p-2"
                style={{ gridColumn: "span 6 / span 6", minHeight: 240 }}
              >
                <NdviChart ndviData={current.ndvi} eviData={current.evi} />
              </section>

              {/* Weather chart */}
              <section
                className="card-surface p-2"
                style={{ gridColumn: "span 6 / span 6", minHeight: 240 }}
              >
                <WeatherChart data={current.weather} />
              </section>

              {/* Land-cover composition — stacked area showing sand shrinking
                  as grass/shrub/forest layers build up over two decades. */}
              <section
                className="card-surface p-2"
                style={{ gridColumn: "span 12 / span 12", minHeight: 300 }}
              >
                <LandCoverChart
                  series={landCover[current.region.id] ?? []}
                  activeYear={selectedYear}
                />
              </section>
            </>
          ) : (
            <>
              {/* Two-region comparison header */}
              <section
                className="px-1 py-2"
                style={{ gridColumn: "span 12 / span 12" }}
              >
                <div className="text-[10px] uppercase tracking-[0.22em] text-[var(--ink-soft)]">
                  双沙地对比 · Comparative Trajectory
                </div>
                <h2 className="mt-1 text-[18px] font-semibold tracking-tight text-[var(--ink)]">
                  科尔沁 vs 浑善达克：谁恢复得更快？
                </h2>
                <p className="mt-1 text-[11px] text-[var(--ink-muted)]">
                  两大重点沙地的年均 NDVI 与沙化风险并列对照，时间滑块同步控制。
                </p>
              </section>

              {/* NDVI comparison */}
              <section
                className="card-surface p-2"
                style={{ gridColumn: "span 6 / span 6", minHeight: 260 }}
              >
                <ComparisonChart
                  regions={comparisonBundles}
                  activeYear={selectedYear}
                  metric="ndvi"
                />
              </section>

              {/* Risk comparison */}
              <section
                className="card-surface p-2"
                style={{ gridColumn: "span 6 / span 6", minHeight: 260 }}
              >
                <ComparisonChart
                  regions={comparisonBundles}
                  activeYear={selectedYear}
                  metric="risk"
                />
              </section>
            </>
          )}
        </div>
      </main>

      <SiteFooter />

      <ChatWidget
        regionHint={selectedId != null ? REGION_ID_TO_ALIAS[selectedId] ?? null : null}
      />
    </div>
  );
}

// --------------- Components ---------------

function RiskHero({
  latest,
  style,
}: {
  latest: RiskRecord | null;
  style?: React.CSSProperties;
}) {
  const level = latest?.risk_level ?? 0;
  const score = latest?.risk_score ?? 0;
  const label = RISK_LEVEL_LABELS[level] ?? "—";
  const color = RISK_LEVEL_COLORS[level] ?? "#a1a1aa";
  const pct = Math.max(0, Math.min(100, score * 100));

  return (
    <section
      className="card-surface relative overflow-hidden px-5 py-4"
      style={style}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.22em] text-[var(--ink-soft)]">
            沙化风险
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-[26px] font-semibold leading-none" style={{ color }}>
              {label}
            </span>
            <span className="num text-sm text-[var(--ink-muted)]">
              score {score.toFixed(2)}
            </span>
          </div>
        </div>
        <div className="flex flex-col items-end">
          <div className="flex gap-0.5">
            {[1, 2, 3, 4].map((i) => (
              <span
                key={i}
                className="h-1.5 w-5 rounded-full"
                style={{
                  backgroundColor: i <= level ? color : "#e7e5e4",
                }}
              />
            ))}
          </div>
          <div className="mt-1 text-[10px] tracking-wide text-[var(--ink-soft)]">
            L{level || "—"}
          </div>
        </div>
      </div>

      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-[var(--line)]">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <div className="num mt-1.5 flex justify-between text-[10px] text-[var(--ink-soft)]">
        <span>低</span>
        <span>中</span>
        <span>高</span>
        <span>极高</span>
      </div>
    </section>
  );
}

function KpiCard({
  label,
  value,
  hint,
  tone,
  style,
  compact,
}: {
  label: string;
  value: string;
  hint: string;
  tone: "moss" | "sand";
  style?: React.CSSProperties;
  compact?: boolean;
}) {
  const accent = tone === "moss" ? "var(--accent-moss)" : "var(--accent-sand)";
  return (
    <section
      className={`card-surface relative overflow-hidden ${
        compact ? "px-3 py-3" : "px-4 py-3"
      }`}
      style={style}
    >
      <div className="text-[10px] uppercase tracking-[0.2em] text-[var(--ink-soft)]">
        {label}
      </div>
      <div
        className={`num mt-1 font-semibold tracking-tight ${
          compact ? "text-[20px]" : "text-[24px]"
        }`}
        style={{ color: accent }}
      >
        {value}
      </div>
      <div className="text-[10px] text-[var(--ink-soft)]">{hint}</div>
    </section>
  );
}

function LayerToggle({
  layerMode,
  onChange,
}: {
  layerMode: MapLayerMode;
  onChange: (m: MapLayerMode) => void;
}) {
  const labels: Record<MapLayerMode, string> = {
    ndvi: "植被覆盖",
    risk: "沙化风险",
    hotspot: "像素热点",
  };
  return (
    <div className="absolute left-3 top-3 flex overflow-hidden rounded-full border border-[var(--line)] bg-white/90 p-0.5 text-[11px] shadow-sm backdrop-blur">
      {(["ndvi", "risk", "hotspot"] as const).map((mode) => (
        <button
          key={mode}
          onClick={() => onChange(mode)}
          className={`rounded-full px-3 py-1 font-medium transition ${
            layerMode === mode
              ? "bg-[var(--ink)] text-white"
              : "text-[var(--ink-muted)] hover:text-[var(--ink)]"
          }`}
        >
          {labels[mode]}
        </button>
      ))}
    </div>
  );
}

function NdviGradientLegend({ title }: { title: string }) {
  // Sample the same sand→green ramp used by RegionMap at a few NDVI stops so
  // the legend reads as a gradient strip with anchor labels. Shared by the
  // polygon-level 植被覆盖 view and the pixel-level 像素热点 view since both
  // map NDVI onto the same ramp.
  const stops = [0.25, 0.29, 0.33, 0.37, 0.42];
  const sand = [212, 165, 116];
  const green = [46, 125, 50];
  const color = (ndvi: number) => {
    const t = Math.max(0, Math.min(1, (ndvi - 0.25) / (0.42 - 0.25)));
    const r = Math.round(sand[0] + (green[0] - sand[0]) * t);
    const g = Math.round(sand[1] + (green[1] - sand[1]) * t);
    const b = Math.round(sand[2] + (green[2] - sand[2]) * t);
    return `rgb(${r}, ${g}, ${b})`;
  };
  return (
    <div className="absolute bottom-3 left-3 rounded-md border border-[var(--line)] bg-white/90 px-3 py-2 text-[10px] shadow-sm backdrop-blur">
      <div className="mb-1 font-semibold tracking-wide text-[var(--ink)]">
        {title}
      </div>
      <div
        className="h-2 w-36 rounded-full"
        style={{
          background: `linear-gradient(to right, ${stops.map(color).join(", ")})`,
        }}
      />
      <div className="num mt-1 flex w-36 justify-between text-[var(--ink-soft)]">
        <span>0.25</span>
        <span>0.33</span>
        <span>0.42</span>
      </div>
    </div>
  );
}

function ProjectInfoPanel({ style }: { style?: React.CSSProperties }) {
  return (
    <section
      className="card-surface card-surface--warm relative overflow-hidden px-6 py-5"
      style={style}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 -bottom-16 h-52 w-52 rounded-full opacity-30"
        style={{
          background:
            "radial-gradient(closest-side, rgba(46,125,50,0.28), transparent)",
        }}
      />
      <div className="text-[10px] uppercase tracking-[0.22em] text-[var(--ink-soft)]">
        项目说明 · About
      </div>
      <h2 className="mt-1 text-[20px] font-semibold tracking-tight text-[var(--ink)]">
        三北防护林 · 沙地遥感监测
      </h2>
      <p className="mt-2 text-[12px] leading-relaxed text-[var(--ink-muted)]">
        以科尔沁与浑善达克两大重点沙地为观测窗口，融合卫星遥感、再分析气象与
        地表覆盖产品，持续追踪植被恢复与沙化风险的时空演变。
      </p>

      <div className="mt-4 grid grid-cols-2 gap-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--ink-soft)]">
            核心指标
          </div>
          <ul className="mt-2 space-y-1.5 text-[11.5px] text-[var(--ink-muted)]">
            <li>
              <span className="font-medium text-[var(--ink)]">NDVI / EVI</span>
              <span className="ml-1 text-[var(--ink-soft)]">年际植被均值</span>
            </li>
            <li>
              <span className="font-medium text-[var(--ink)]">FVC</span>
              <span className="ml-1 text-[var(--ink-soft)]">植被覆盖度</span>
            </li>
            <li>
              <span className="font-medium text-[var(--ink)]">碳密度</span>
              <span className="ml-1 text-[var(--ink-soft)]">gC/m²</span>
            </li>
            <li>
              <span className="font-medium text-[var(--ink)]">风险得分</span>
              <span className="ml-1 text-[var(--ink-soft)]">
                气象 × 植被加权
              </span>
            </li>
          </ul>
        </div>

        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--ink-soft)]">
            数据来源
          </div>
          <ul className="mt-2 space-y-1.5 text-[11.5px] text-[var(--ink-muted)]">
            <li>
              <span className="font-medium text-[var(--ink)]">MODIS</span>
              <span className="ml-1 text-[var(--ink-soft)]">
                MOD13Q1 / MCD15A3H
              </span>
            </li>
            <li>
              <span className="font-medium text-[var(--ink)]">Landsat</span>
              <span className="ml-1 text-[var(--ink-soft)]">
                Collection 2 L2
              </span>
            </li>
            <li>
              <span className="font-medium text-[var(--ink)]">ERA5-Land</span>
              <span className="ml-1 text-[var(--ink-soft)]">月度气象</span>
            </li>
            <li>
              <span className="font-medium text-[var(--ink)]">ESA WorldCover</span>
              <span className="ml-1 text-[var(--ink-soft)]">沙地边界</span>
            </li>
          </ul>
        </div>
      </div>

      <div className="mt-5 border-t border-[var(--line)] pt-3">
        <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--ink-soft)]">
          计算方法
        </div>
        <p className="mt-1.5 text-[11.5px] leading-relaxed text-[var(--ink-muted)]">
          各子区的年均 NDVI 以 UTC 年份聚合像元均值；沙化风险由植被衰退趋势、
          降水距平、温度异常与土壤湿度四项归一化后加权，映射至 L1–L4 四级。
        </p>
      </div>
    </section>
  );
}

function CompareToggle({
  enabled,
  onToggle,
}: {
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className={`absolute right-3 top-3 rounded-full border px-3 py-1 text-[11px] font-medium shadow-sm transition ${
        enabled
          ? "border-[var(--ink)] bg-[var(--ink)] text-white"
          : "border-[var(--line)] bg-white/90 text-[var(--ink-muted)] hover:text-[var(--ink)]"
      }`}
    >
      {enabled ? "退出对比" : "对比 Compare"}
    </button>
  );
}

function CompareYearControls({
  beforeYear,
  afterYear,
  onBeforeChange,
  onAfterChange,
}: {
  beforeYear: number;
  afterYear: number;
  onBeforeChange: (y: number) => void;
  onAfterChange: (y: number) => void;
}) {
  // Landsat 8 begins 2013; Landsat 5/7 cover earlier years but use different
  // bands — backend handles the switch, so we expose the full range the API
  // accepts.
  const years: number[] = [];
  for (let y = 1990; y <= 2025; y += 1) years.push(y);

  return (
    <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full border border-[var(--line)] bg-white/90 px-3 py-1.5 text-[11px] shadow-sm backdrop-blur">
      <label className="flex items-center gap-1.5">
        <span className="text-[var(--ink-soft)]">对比前</span>
        <select
          value={beforeYear}
          onChange={(e) => onBeforeChange(Number(e.target.value))}
          className="rounded border border-[var(--line)] bg-white px-1.5 py-0.5 text-[11px] font-medium text-[var(--ink)]"
        >
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </label>
      <span className="text-[var(--ink-soft)]">→</span>
      <label className="flex items-center gap-1.5">
        <span className="text-[var(--ink-soft)]">对比后</span>
        <select
          value={afterYear}
          onChange={(e) => onAfterChange(Number(e.target.value))}
          className="rounded border border-[var(--line)] bg-white px-1.5 py-0.5 text-[11px] font-medium text-[var(--ink)]"
        >
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function RiskLegend() {
  return (
    <div className="absolute bottom-3 left-3 flex flex-col gap-1 rounded-md border border-[var(--line)] bg-white/90 px-3 py-2 text-[10px] shadow-sm backdrop-blur">
      <div className="mb-1 font-semibold tracking-wide text-[var(--ink)]">
        风险等级
      </div>
      {[4, 3, 2, 1].map((lvl) => (
        <div key={lvl} className="flex items-center gap-2">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ backgroundColor: RISK_LEVEL_COLORS[lvl] }}
          />
          <span className="text-[var(--ink-muted)]">
            L{lvl} {RISK_LEVEL_LABELS[lvl]}
          </span>
        </div>
      ))}
    </div>
  );
}

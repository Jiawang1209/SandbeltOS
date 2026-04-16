"use client";

import { useEffect, useState, useCallback } from "react";
import RegionMap from "@/components/RegionMap";
import NdviChart from "@/components/NdviChart";
import WeatherChart from "@/components/WeatherChart";
import {
  fetchRegions,
  fetchTimeseries,
  fetchWeather,
  type RegionsGeoJSON,
  type TimeseriesRecord,
  type WeatherRecord,
  type Region,
} from "@/lib/api";

interface RegionData {
  region: Region;
  ndvi: TimeseriesRecord[];
  evi: TimeseriesRecord[];
  weather: WeatherRecord[];
}

export default function DashboardPage() {
  const [regions, setRegions] = useState<RegionsGeoJSON | null>(null);
  const [regionDataMap, setRegionDataMap] = useState<Record<number, RegionData>>({});
  const [selectedId, setSelectedId] = useState<number>(1);
  const [ndviSummary, setNdviSummary] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const regionsRes = await fetchRegions();
        setRegions(regionsRes);

        // Load data for subregions only (not the overall shelterbelt)
        const subregions = regionsRes.features.filter(
          (f) => f.properties.level === "subregion"
        );

        const dataMap: Record<number, RegionData> = {};
        const summaries: Record<number, number> = {};

        await Promise.all(
          subregions.map(async (f) => {
            const id = f.properties.id;
            const [ndviRes, eviRes, weatherRes] = await Promise.all([
              fetchTimeseries(id, "ndvi"),
              fetchTimeseries(id, "evi"),
              fetchWeather(id),
            ]);
            dataMap[id] = {
              region: ndviRes.region,
              ndvi: ndviRes.data,
              evi: eviRes.data,
              weather: weatherRes.data,
            };
            summaries[id] =
              ndviRes.data.length > 0
                ? ndviRes.data.reduce((s, d) => s + d.value, 0) / ndviRes.data.length
                : 0;
          })
        );

        setRegionDataMap(dataMap);
        setNdviSummary(summaries);
        setSelectedId(subregions[0]?.properties.id ?? 1);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleSelectRegion = useCallback((id: number) => {
    setSelectedId(id);
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-50">
        <div className="text-zinc-500">加载数据中...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-50">
        <div className="text-red-500">加载失败: {error}</div>
      </div>
    );
  }

  const current = regionDataMap[selectedId];
  const subregionIds = Object.keys(regionDataMap).map(Number);

  return (
    <div className="flex h-screen flex-col bg-zinc-50">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-5 py-3">
        <div className="flex items-center gap-3">
          <a href="/" className="text-lg font-bold tracking-tight text-zinc-900">
            SandbeltOS
          </a>
          <span className="text-sm text-zinc-400">|</span>
          <span className="text-sm text-zinc-600">三北防护林生态监测</span>
        </div>

        {/* Region tabs */}
        <div className="flex items-center gap-1">
          {subregionIds.map((id) => {
            const rd = regionDataMap[id];
            return (
              <button
                key={id}
                onClick={() => setSelectedId(id)}
                className={`rounded-md px-3 py-1.5 text-sm transition ${
                  id === selectedId
                    ? "bg-green-600 text-white font-medium"
                    : "text-zinc-600 hover:bg-zinc-100"
                }`}
              >
                {rd.region.name}
              </button>
            );
          })}
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Map */}
        <div className="flex-1 p-3">
          <div className="h-full rounded-lg border border-zinc-200 bg-white shadow-sm overflow-hidden">
            <RegionMap
              regions={regions}
              ndviSummary={ndviSummary}
              selectedRegionId={selectedId}
              onSelectRegion={handleSelectRegion}
            />
          </div>
        </div>

        {/* Right panel */}
        {current && (
          <div className="flex w-[480px] flex-col gap-3 overflow-y-auto p-3 pl-0">
            {/* Region header */}
            <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
              <h2 className="text-lg font-semibold text-zinc-900">
                {current.region.name}
              </h2>
              <p className="text-sm text-zinc-500">
                {current.region.area_km2?.toLocaleString()} km² · {current.region.level}
              </p>
            </div>

            {/* Stats cards */}
            <div className="grid grid-cols-3 gap-3">
              <StatCard
                label="NDVI 均值"
                value={
                  current.ndvi.length > 0
                    ? (
                        current.ndvi.reduce((s, d) => s + d.value, 0) /
                        current.ndvi.length
                      ).toFixed(3)
                    : "—"
                }
                sub="2020-2024"
                color="text-green-600"
              />
              <StatCard
                label="年均降水"
                value={
                  current.weather.length > 0
                    ? `${Math.round(
                        current.weather.reduce((s, d) => s + d.precipitation, 0) / 5
                      )}`
                    : "—"
                }
                sub="mm/年"
                color="text-blue-600"
              />
              <StatCard
                label="年均温度"
                value={
                  current.weather.length > 0
                    ? `${(
                        current.weather.reduce((s, d) => s + d.temperature, 0) /
                        current.weather.length
                      ).toFixed(1)}`
                    : "—"
                }
                sub="°C"
                color="text-red-500"
              />
            </div>

            {/* NDVI chart */}
            <div className="h-[260px] rounded-lg border border-zinc-200 bg-white p-2 shadow-sm">
              <NdviChart ndviData={current.ndvi} eviData={current.evi} />
            </div>

            {/* Weather chart */}
            <div className="h-[260px] rounded-lg border border-zinc-200 bg-white p-2 shadow-sm">
              <WeatherChart data={current.weather} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub: string;
  color: string;
}) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3 shadow-sm">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className={`mt-1 text-xl font-semibold ${color}`}>{value}</div>
      <div className="text-xs text-zinc-400">{sub}</div>
    </div>
  );
}

"use client";

import ReactECharts from "echarts-for-react";
import type { TimeseriesRecord, RiskRecord, Region } from "@/lib/api";

interface RegionBundle {
  region: Region;
  ndvi: TimeseriesRecord[];
  risk: RiskRecord[];
}

interface ComparisonChartProps {
  regions: RegionBundle[];
  activeYear?: number | null;
  metric?: "ndvi" | "risk";
}

interface YearPoint {
  year: number;
  mean: number;
}

function yearlyMean(points: Array<[string, number]>): YearPoint[] {
  const buckets = new Map<number, number[]>();
  for (const [t, v] of points) {
    const y = new Date(t).getUTCFullYear();
    if (!Number.isFinite(y) || !Number.isFinite(v)) continue;
    const arr = buckets.get(y) ?? buckets.set(y, []).get(y)!;
    arr.push(v);
  }
  return [...buckets.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([year, vs]) => ({
      year,
      mean: vs.reduce((s, v) => s + v, 0) / vs.length,
    }));
}

function paddedRange(vals: number[], padFrac = 0.25): [number, number] {
  if (vals.length === 0) return [0, 1];
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const pad = Math.max((hi - lo) * padFrac, 0.02);
  const step = 0.05;
  return [
    Math.max(0, Math.floor((lo - pad) / step) * step),
    Math.min(1, Math.ceil((hi + pad) / step) * step),
  ];
}

function pctChange(years: YearPoint[]): number | null {
  if (years.length < 2) return null;
  const first = years[0].mean;
  const last = years[years.length - 1].mean;
  if (first === 0) return null;
  return ((last - first) / Math.abs(first)) * 100;
}

// Distinct palettes so the two regions read apart at a glance without both
// feeling "green" — Horqin leans forest, Otindag leans warm/ochre.
const REGION_COLORS: Record<string, string> = {
  "科尔沁沙地": "#166534",
  "浑善达克沙地": "#b45309",
};

function regionColor(name: string, idx: number): string {
  return REGION_COLORS[name] ?? (idx === 0 ? "#166534" : "#b45309");
}

export default function ComparisonChart({
  regions,
  activeYear,
  metric = "ndvi",
}: ComparisonChartProps) {
  const perRegion = regions.map((rb, idx) => {
    const raw =
      metric === "ndvi"
        ? rb.ndvi.map<[string, number]>((d) => [d.time, d.value])
        : rb.risk.map<[string, number]>((d) => [d.time, d.risk_score]);
    const yearsAll = yearlyMean(raw);
    return {
      region: rb.region,
      color: regionColor(rb.region.name, idx),
      yearsAll,
    };
  });

  const allYears = perRegion.flatMap((r) => r.yearsAll);
  const firstYear = allYears[0]?.year ?? 0;
  const lastYear = allYears[allYears.length - 1]?.year ?? 0;
  const minYear = allYears.length > 0 ? Math.min(...allYears.map((p) => p.year)) : firstYear;
  const maxYear = allYears.length > 0 ? Math.max(...allYears.map((p) => p.year)) : lastYear;

  const clipYear = activeYear ?? maxYear ?? Number.POSITIVE_INFINITY;

  const [yMin, yMax] = paddedRange(allYears.map((p) => p.mean));

  const series = perRegion.map((r) => {
    const clipped = r.yearsAll.filter((p) => p.year <= clipYear);
    const data = clipped.map((p) => [p.year, p.mean] as [number, number]);
    const delta = pctChange(clipped);
    const last = data[data.length - 1];
    return {
      name: r.region.name,
      type: "line" as const,
      data,
      smooth: true,
      symbol: "circle",
      symbolSize: 7,
      lineStyle: { width: 3, color: r.color },
      itemStyle: { color: r.color },
      areaStyle: {
        color: {
          type: "linear" as const,
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: `${r.color}40` },
            { offset: 1, color: `${r.color}05` },
          ],
        },
      },
      markPoint: last
        ? {
            symbol: "roundRect",
            symbolSize: [64, 20],
            symbolOffset: [0, metric === "ndvi" ? -20 : 20],
            label: {
              formatter:
                delta != null
                  ? `${delta > 0 ? "+" : ""}${delta.toFixed(1)}%`
                  : "—",
              color: "#fff",
              fontSize: 11,
              fontWeight: 700,
            },
            itemStyle: { color: r.color },
            data: [{ coord: last }],
          }
        : undefined,
    };
  });

  const title =
    metric === "ndvi"
      ? "两大沙地 · NDVI 恢复轨迹"
      : "两大沙地 · 沙化风险演变";

  const option = {
    title: {
      text: title,
      subtext: "科尔沁沙地 vs 浑善达克沙地",
      left: 8,
      top: 4,
      textStyle: { fontSize: 14, fontWeight: 600, color: "#18181b" },
      subtextStyle: { fontSize: 10, color: "#78716c" },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter(
        params: Array<{
          seriesName: string;
          value: [number, number];
          marker: string;
        }>
      ) {
        const year = params[0].value[0];
        const lines = params.map(
          (p) => `${p.marker} ${p.seriesName}: ${p.value[1].toFixed(3)}`
        );
        return `<strong>${year}</strong><br/>${lines.join("<br/>")}`;
      },
    },
    legend: {
      data: perRegion.map((r) => r.region.name),
      top: 4,
      right: 8,
      textStyle: { fontSize: 11 },
      itemGap: 14,
    },
    grid: { left: 44, right: 24, top: 48, bottom: 30 },
    xAxis: {
      type: "value",
      min: minYear,
      max: maxYear,
      interval: 1,
      axisLabel: { fontSize: 10, formatter: (v: number) => `${v}` },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        fontSize: 10,
        color: metric === "ndvi" ? "#166534" : "#b91c1c",
        formatter: (v: number) => v.toFixed(2),
      },
      splitLine: { lineStyle: { color: "#f1f1f1", type: "dashed" } },
      min: yMin,
      max: yMax,
    },
    series,
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: "100%", width: "100%" }}
      notMerge
    />
  );
}

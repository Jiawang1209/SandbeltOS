"use client";

import ReactECharts from "echarts-for-react";
import type { TimeseriesRecord, RiskRecord } from "@/lib/api";

interface AchievementChartProps {
  ndvi: TimeseriesRecord[];
  risk: RiskRecord[];
  // When provided, clips both series to years ≤ activeYear so the chart
  // animates forward as the map's time slider plays.
  activeYear?: number | null;
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

// Pad around the observed range so the trend fills the canvas but the
// starting value still reads as whatever it actually is (not a forced 100).
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

export default function AchievementChart({
  ndvi,
  risk,
  activeYear,
}: AchievementChartProps) {
  const ndviYearsAll = yearlyMean(ndvi.map((d) => [d.time, d.value]));
  const riskYearsAll = yearlyMean(risk.map((d) => [d.time, d.risk_score]));

  // Y-axis range is always computed over the full span so the axes don't
  // rescale while scrubbing — only the visible line clips forward.
  const [ndviMin, ndviMax] = paddedRange(ndviYearsAll.map((p) => p.mean));
  const [riskMin, riskMax] = paddedRange(riskYearsAll.map((p) => p.mean));

  const firstYear = ndviYearsAll[0]?.year ?? riskYearsAll[0]?.year;
  const lastYear =
    ndviYearsAll[ndviYearsAll.length - 1]?.year ??
    riskYearsAll[riskYearsAll.length - 1]?.year;
  const span = firstYear && lastYear ? lastYear - firstYear : 0;

  const clipYear = activeYear ?? lastYear ?? Number.POSITIVE_INFINITY;
  const ndviYears = ndviYearsAll.filter((p) => p.year <= clipYear);
  const riskYears = riskYearsAll.filter((p) => p.year <= clipYear);

  const ndviData = ndviYears.map((p) => [p.year, p.mean] as [number, number]);
  const riskData = riskYears.map((p) => [p.year, p.mean] as [number, number]);

  const ndviDelta = pctChange(ndviYears);
  const riskDelta = pctChange(riskYears);

  const lastNdvi = ndviData[ndviData.length - 1];
  const lastRisk = riskData[riskData.length - 1];

  const option = {
    title: {
      text: `近 ${span || "—"} 年治沙成效`,
      subtext: "三北防护林 · 退耕还林还草 · 综合治理",
      left: 8,
      top: 4,
      textStyle: { fontSize: 14, fontWeight: 600, color: "#18181b" },
      subtextStyle: { fontSize: 10, color: "#78716c" },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter(params: Array<{ seriesName: string; value: [number, number]; marker: string }>) {
        const year = params[0].value[0];
        const lines = params.map(
          (p) => `${p.marker} ${p.seriesName}: ${p.value[1].toFixed(3)}`
        );
        return `<strong>${year}</strong><br/>${lines.join("<br/>")}`;
      },
    },
    legend: {
      data: ["植被指数 NDVI", "沙化风险 Score"],
      top: 4,
      right: 8,
      textStyle: { fontSize: 11 },
      itemGap: 14,
    },
    grid: { left: 44, right: 48, top: 48, bottom: 30 },
    xAxis: {
      type: "value",
      min: firstYear,
      max: lastYear,
      interval: 1,
      axisLabel: { fontSize: 10, formatter: (v: number) => `${v}` },
      splitLine: { show: false },
    },
    yAxis: [
      {
        type: "value",
        position: "left",
        axisLabel: {
          fontSize: 10,
          color: "#166534",
          formatter: (v: number) => v.toFixed(2),
        },
        splitLine: { lineStyle: { color: "#f1f1f1", type: "dashed" } },
        min: ndviMin,
        max: ndviMax,
      },
      {
        type: "value",
        position: "right",
        axisLabel: {
          fontSize: 10,
          color: "#b91c1c",
          formatter: (v: number) => v.toFixed(2),
        },
        splitLine: { show: false },
        min: riskMin,
        max: riskMax,
        inverse: false,
      },
    ],
    series: [
      {
        name: "植被指数 NDVI",
        type: "line",
        yAxisIndex: 0,
        data: ndviData,
        smooth: true,
        symbol: "circle",
        symbolSize: 7,
        lineStyle: { width: 3, color: "#166534" },
        itemStyle: { color: "#166534" },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(22, 101, 52, 0.28)" },
              { offset: 1, color: "rgba(22, 101, 52, 0.02)" },
            ],
          },
        },
        markPoint: lastNdvi
          ? {
              symbol: "roundRect",
              symbolSize: [64, 20],
              symbolOffset: [0, -20],
              label: {
                formatter:
                  ndviDelta != null
                    ? `${ndviDelta > 0 ? "+" : ""}${ndviDelta.toFixed(1)}%`
                    : "—",
                color: "#fff",
                fontSize: 11,
                fontWeight: 700,
              },
              itemStyle: { color: "#166534" },
              data: [{ coord: lastNdvi }],
            }
          : undefined,
      },
      {
        name: "沙化风险 Score",
        type: "line",
        yAxisIndex: 1,
        data: riskData,
        smooth: true,
        symbol: "circle",
        symbolSize: 7,
        lineStyle: { width: 3, color: "#b91c1c" },
        itemStyle: { color: "#b91c1c" },
        markPoint: lastRisk
          ? {
              symbol: "roundRect",
              symbolSize: [64, 20],
              symbolOffset: [0, 20],
              label: {
                formatter:
                  riskDelta != null
                    ? `${riskDelta > 0 ? "+" : ""}${riskDelta.toFixed(1)}%`
                    : "—",
                color: "#fff",
                fontSize: 11,
                fontWeight: 700,
              },
              itemStyle: { color: "#b91c1c" },
              data: [{ coord: lastRisk }],
            }
          : undefined,
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: "100%", width: "100%" }}
      notMerge
    />
  );
}

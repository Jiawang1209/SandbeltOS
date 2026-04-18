"use client";

import ReactECharts from "echarts-for-react";
import type { TimeseriesRecord } from "@/lib/api";

interface NdviChartProps {
  ndviData: TimeseriesRecord[];
  eviData: TimeseriesRecord[];
}

export default function NdviChart({ ndviData, eviData }: NdviChartProps) {
  const allVals = [...ndviData, ...eviData].map((d) => d.value);
  const dataMax = allVals.length ? Math.max(...allVals) : 0.5;
  const yMax = dataMax >= 0.6
    ? 1
    : Math.max(0.5, Math.ceil((dataMax + 0.1) * 10) / 10);

  // Annual mean overlay — plotted mid-year so the bold trend line sits on top
  // of the seasonal oscillation.
  const yearBuckets = new Map<number, number[]>();
  for (const d of ndviData) {
    const y = new Date(d.time).getUTCFullYear();
    if (!Number.isFinite(y)) continue;
    (yearBuckets.get(y) ?? yearBuckets.set(y, []).get(y)!).push(d.value);
  }
  const annualMean = [...yearBuckets.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([y, vs]) => [
      `${y}-07-01`,
      vs.reduce((s, v) => s + v, 0) / vs.length,
    ] as [string, number]);

  const option = {
    title: {
      text: "植被指数时序",
      textStyle: { fontSize: 14, fontWeight: 600, color: "#18181b" },
      left: 8,
      top: 4,
    },
    tooltip: {
      trigger: "axis",
      formatter(params: Array<{ seriesName: string; value: [string, number]; marker: string }>) {
        const date = params[0].value[0];
        const lines = params.map(
          (p) => `${p.marker} ${p.seriesName}: ${p.value[1].toFixed(4)}`
        );
        return `${date}<br/>${lines.join("<br/>")}`;
      },
    },
    legend: {
      data: ["NDVI", "EVI", "NDVI 年均趋势"],
      top: 4,
      right: 8,
      textStyle: { fontSize: 12 },
    },
    grid: { left: 44, right: 16, top: 44, bottom: 36 },
    xAxis: {
      type: "time",
      axisLabel: { fontSize: 10, hideOverlap: true },
      splitLine: { show: true, lineStyle: { color: "#f1f1f1" } },
    },
    yAxis: {
      type: "value",
      axisLabel: { fontSize: 10 },
      min: 0,
      max: yMax,
    },
    series: [
      {
        name: "NDVI",
        type: "line",
        data: ndviData.map((d) => [d.time, d.value]),
        smooth: true,
        symbol: "none",
        lineStyle: { width: 2, color: "#16a34a" },
        areaStyle: { color: "rgba(22, 163, 74, 0.08)" },
      },
      {
        name: "EVI",
        type: "line",
        data: eviData.map((d) => [d.time, d.value]),
        smooth: true,
        symbol: "none",
        lineStyle: { width: 2, color: "#0ea5e9" },
      },
      {
        name: "NDVI 年均趋势",
        type: "line",
        data: annualMean,
        smooth: false,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { width: 3, color: "#166534" },
        itemStyle: { color: "#166534" },
        z: 3,
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

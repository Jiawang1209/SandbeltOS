"use client";

import ReactECharts from "echarts-for-react";
import type { LandCoverYear } from "@/lib/api";

interface LandCoverChartProps {
  series: LandCoverYear[];
  activeYear?: number | null;
}

// Stacked-area order from bottom to top — barren at the base so the visual
// story reads as "sand being covered up" as greener layers grow on top.
const BUCKETS = [
  { key: "barren", label: "裸地 · 沙地", color: "#d4a574" },
  { key: "crop", label: "耕地", color: "#e4b363" },
  { key: "grass", label: "草地", color: "#84a98c" },
  { key: "shrub", label: "灌木 · 疏林", color: "#52796f" },
  { key: "forest", label: "林地", color: "#2f3e46" },
  { key: "other", label: "其他", color: "#adb5bd" },
] as const;

export default function LandCoverChart({
  series,
  activeYear,
}: LandCoverChartProps) {
  if (series.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm text-[var(--ink-soft)]">
        暂无土地覆盖数据
      </div>
    );
  }

  const years = series.map((s) => s.year);

  const echartSeries = BUCKETS.map((b) => ({
    name: b.label,
    type: "line",
    stack: "total",
    smooth: 0.3,
    showSymbol: false,
    areaStyle: { color: b.color, opacity: 0.92 },
    lineStyle: { color: b.color, width: 0 },
    emphasis: { focus: "series" },
    data: series.map((s) => +(s[b.key] * 100).toFixed(2)),
    markLine:
      b.key === "barren" && activeYear != null
        ? {
            symbol: "none",
            silent: true,
            lineStyle: { color: "#111", width: 1, type: "dashed" },
            data: [{ xAxis: activeYear, label: { show: false } }],
          }
        : undefined,
  }));

  const option = {
    title: {
      text: "土地覆盖演变",
      subtext: "MCD12Q1 · IGBP · 500m",
      textStyle: { fontSize: 14, fontWeight: 600, color: "#18181b" },
      subtextStyle: { fontSize: 10, color: "#8b8680" },
      left: 8,
      top: 4,
    },
    tooltip: {
      trigger: "axis",
      valueFormatter: (v: number) => `${v.toFixed(1)}%`,
    },
    legend: {
      data: BUCKETS.map((b) => b.label),
      top: 4,
      right: 8,
      textStyle: { fontSize: 11 },
      itemWidth: 12,
      itemHeight: 8,
    },
    grid: { left: 44, right: 16, top: 56, bottom: 28 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: years,
      axisLabel: { fontSize: 10, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { fontSize: 10, formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#f1f1f1" } },
    },
    series: echartSeries,
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: "100%", width: "100%" }}
      opts={{ renderer: "canvas" }}
      notMerge
    />
  );
}

"use client";

import ReactECharts from "echarts-for-react";
import {
  RISK_LEVEL_COLORS,
  RISK_LEVEL_LABELS,
  type YearlyProjection,
} from "@/lib/api";

interface ScenarioChartProps {
  yearly: YearlyProjection[];
}

/**
 * Multi-line scenario projection chart.
 *
 * Three series share the 0-100 axis:
 *   * FVC % (植被覆盖度) — green
 *   * Soil moisture × 100 (土壤水分,扩展至同一量级) — brown
 *   * Risk score × 100 — red
 *
 * Background bands per-year are tinted by `risk_level` so the eye picks
 * up the risk trajectory at a glance.
 */
export default function ScenarioChart({ yearly }: ScenarioChartProps) {
  const years = yearly.map((p) => p.year);
  const fvcPct = yearly.map((p) => Number((p.fvc * 100).toFixed(2)));
  const smPct = yearly.map((p) => Number((p.soil_moisture * 100).toFixed(2)));
  const riskPct = yearly.map((p) => Number((p.risk_score * 100).toFixed(1)));

  // Per-year background tint based on risk_level. ECharts uses `markArea`
  // with two coordinates per band.
  const markAreaData = yearly.map((p) => [
    {
      xAxis: p.year - 0.5,
      itemStyle: { color: hexToRgba(RISK_LEVEL_COLORS[p.risk_level] ?? "#a8a29e", 0.08) },
    },
    { xAxis: p.year + 0.5 },
  ]);

  const option = {
    title: {
      text: "造林情景投影",
      textStyle: { fontSize: 14, fontWeight: 600, color: "#18181b" },
      left: 8,
      top: 4,
    },
    tooltip: {
      trigger: "axis",
      formatter(params: Array<{ axisValue: string; seriesName: string; value: number; marker: string }>) {
        const year = params[0].axisValue;
        const idx = years.indexOf(Number(year));
        const p = idx >= 0 ? yearly[idx] : null;
        const lines = params.map(
          (q) => `${q.marker} ${q.seriesName}: ${q.value.toFixed(2)}`
        );
        const riskLine = p
          ? `<br/><span style="color: ${RISK_LEVEL_COLORS[p.risk_level]}">●</span> 风险等级: ${
              RISK_LEVEL_LABELS[p.risk_level] ?? "—"
            } (L${p.risk_level})${p.warning ? `<br/><span style="color:#b45309">⚠ ${p.warning}</span>` : ""}`
          : "";
        return `第 ${year} 年<br/>${lines.join("<br/>")}${riskLine}`;
      },
    },
    legend: {
      data: ["植被覆盖度 (%)", "土壤水分 ×100", "风险得分 ×100"],
      top: 4,
      right: 8,
      textStyle: { fontSize: 11 },
    },
    grid: { left: 36, right: 16, top: 44, bottom: 36 },
    xAxis: {
      type: "category",
      data: years,
      name: "年",
      nameTextStyle: { fontSize: 10, color: "#71717a" },
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { fontSize: 10, formatter: "{value}" },
      splitLine: { lineStyle: { color: "#f1f1f1" } },
    },
    series: [
      {
        name: "植被覆盖度 (%)",
        type: "line",
        data: fvcPct,
        smooth: true,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { width: 2.5, color: "#16a34a" },
        itemStyle: { color: "#16a34a" },
        markArea: { silent: true, data: markAreaData },
      },
      {
        name: "土壤水分 ×100",
        type: "line",
        data: smPct,
        smooth: true,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { width: 2, color: "#a16207" },
        itemStyle: { color: "#a16207" },
      },
      {
        name: "风险得分 ×100",
        type: "line",
        data: riskPct,
        smooth: true,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { width: 2, color: "#dc2626" },
        itemStyle: { color: "#dc2626" },
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

function hexToRgba(hex: string, alpha: number): string {
  const m = hex.replace("#", "");
  const r = parseInt(m.slice(0, 2), 16);
  const g = parseInt(m.slice(2, 4), 16);
  const b = parseInt(m.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

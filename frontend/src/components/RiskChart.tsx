"use client";

import ReactECharts from "echarts-for-react";
import { RISK_LEVEL_COLORS, type RiskRecord } from "@/lib/api";

interface RiskChartProps {
  data: RiskRecord[];
}

export default function RiskChart({ data }: RiskChartProps) {
  const option = {
    title: {
      text: "沙化风险趋势",
      textStyle: { fontSize: 14, fontWeight: 600, color: "#18181b" },
      left: 8,
      top: 4,
    },
    tooltip: {
      trigger: "axis",
      formatter(params: Array<{ value: [string, number]; marker: string }>) {
        const p = params[0];
        const date = p.value[0];
        const score = p.value[1];
        const level = levelFromScore(score);
        return `${date}<br/>${p.marker} score: ${score.toFixed(2)}<br/>等级: L${level}`;
      },
    },
    grid: { left: 44, right: 16, top: 30, bottom: 36 },
    xAxis: { type: "time", axisLabel: { fontSize: 10 } },
    yAxis: {
      type: "value",
      min: 0,
      max: 1,
      axisLabel: { fontSize: 10 },
      splitLine: { lineStyle: { color: "#f4f4f5" } },
    },
    visualMap: {
      show: false,
      dimension: 1,
      pieces: [
        { gt: 0.75, lte: 1.01, color: RISK_LEVEL_COLORS[4] },
        { gt: 0.5, lte: 0.75, color: RISK_LEVEL_COLORS[3] },
        { gt: 0.25, lte: 0.5, color: RISK_LEVEL_COLORS[2] },
        { gte: 0, lte: 0.25, color: RISK_LEVEL_COLORS[1] },
      ],
    },
    markLine: {
      silent: true,
      symbol: "none",
      data: [
        { yAxis: 0.25, lineStyle: { type: "dashed", color: "#d4d4d8" } },
        { yAxis: 0.5, lineStyle: { type: "dashed", color: "#d4d4d8" } },
        { yAxis: 0.75, lineStyle: { type: "dashed", color: "#d4d4d8" } },
      ],
    },
    series: [
      {
        name: "risk_score",
        type: "line",
        smooth: true,
        symbol: "none",
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.15 },
        data: data.map((d) => [d.time, d.risk_score]),
      },
    ],
    dataZoom: [{ type: "inside", start: 0, end: 100 }],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: "100%", width: "100%" }}
      notMerge
    />
  );
}

function levelFromScore(s: number): number {
  if (s < 0.25) return 1;
  if (s < 0.5) return 2;
  if (s < 0.75) return 3;
  return 4;
}

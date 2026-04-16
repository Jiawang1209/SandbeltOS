"use client";

import ReactECharts from "echarts-for-react";
import type { TimeseriesRecord } from "@/lib/api";

interface NdviChartProps {
  ndviData: TimeseriesRecord[];
  eviData: TimeseriesRecord[];
}

export default function NdviChart({ ndviData, eviData }: NdviChartProps) {
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
      data: ["NDVI", "EVI"],
      top: 4,
      right: 8,
      textStyle: { fontSize: 12 },
    },
    grid: { left: 50, right: 16, top: 44, bottom: 36 },
    xAxis: {
      type: "time",
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: "value",
      name: "指数值",
      nameTextStyle: { fontSize: 10 },
      axisLabel: { fontSize: 10 },
      min: 0,
      max: 0.5,
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
    ],
    dataZoom: [
      {
        type: "inside",
        start: 0,
        end: 100,
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

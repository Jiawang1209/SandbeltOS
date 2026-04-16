"use client";

import ReactECharts from "echarts-for-react";
import type { WeatherRecord } from "@/lib/api";

interface WeatherChartProps {
  data: WeatherRecord[];
}

export default function WeatherChart({ data }: WeatherChartProps) {
  // Downsample daily data to monthly averages for readability
  const monthly = aggregateMonthly(data);

  const option = {
    title: {
      text: "气象数据",
      textStyle: { fontSize: 14, fontWeight: 600, color: "#18181b" },
      left: 8,
      top: 4,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
    },
    legend: {
      data: ["温度 (°C)", "降水 (mm)", "风速 (m/s)"],
      top: 4,
      right: 8,
      textStyle: { fontSize: 11 },
    },
    grid: { left: 55, right: 55, top: 44, bottom: 36 },
    xAxis: {
      type: "category",
      data: monthly.map((d) => d.month),
      axisLabel: { fontSize: 10, rotate: 45 },
    },
    yAxis: [
      {
        type: "value",
        name: "°C / m/s",
        nameTextStyle: { fontSize: 10 },
        axisLabel: { fontSize: 10 },
      },
      {
        type: "value",
        name: "mm",
        nameTextStyle: { fontSize: 10 },
        axisLabel: { fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "温度 (°C)",
        type: "line",
        data: monthly.map((d) => d.temperature),
        smooth: true,
        symbol: "none",
        lineStyle: { width: 2, color: "#ef4444" },
      },
      {
        name: "降水 (mm)",
        type: "bar",
        yAxisIndex: 1,
        data: monthly.map((d) => d.precipitation),
        itemStyle: { color: "rgba(59, 130, 246, 0.6)" },
        barMaxWidth: 12,
      },
      {
        name: "风速 (m/s)",
        type: "line",
        data: monthly.map((d) => d.wind_speed),
        smooth: true,
        symbol: "none",
        lineStyle: { width: 1.5, color: "#a855f7", type: "dashed" },
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

interface MonthlyAgg {
  month: string;
  temperature: number;
  precipitation: number;
  wind_speed: number;
}

function aggregateMonthly(data: WeatherRecord[]): MonthlyAgg[] {
  const buckets = new Map<
    string,
    { temps: number[]; precips: number[]; winds: number[] }
  >();

  for (const d of data) {
    const month = d.time.slice(0, 7); // "YYYY-MM"
    if (!buckets.has(month)) {
      buckets.set(month, { temps: [], precips: [], winds: [] });
    }
    const b = buckets.get(month)!;
    b.temps.push(d.temperature);
    b.precips.push(d.precipitation);
    b.winds.push(d.wind_speed);
  }

  const result: MonthlyAgg[] = [];
  for (const [month, b] of buckets) {
    const avg = (arr: number[]) =>
      Math.round((arr.reduce((s, v) => s + v, 0) / arr.length) * 10) / 10;
    const sum = (arr: number[]) =>
      Math.round(arr.reduce((s, v) => s + v, 0) * 10) / 10;
    result.push({
      month,
      temperature: avg(b.temps),
      precipitation: sum(b.precips),
      wind_speed: avg(b.winds),
    });
  }

  return result;
}

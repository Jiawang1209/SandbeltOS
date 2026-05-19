"use client";

import ReactECharts from "echarts-for-react";
import type { TimeseriesRecord } from "@/lib/api";

interface LstSmapChartProps {
  lstData: TimeseriesRecord[];
  smapData: TimeseriesRecord[];
}

export default function LstSmapChart({ lstData, smapData }: LstSmapChartProps) {
  const lstMonthly = aggregateMonthly(lstData);
  const smapMonthly = aggregateMonthly(smapData);

  // Union of months so both axes line up even when a series is missing a bucket.
  const months = Array.from(
    new Set([...lstMonthly.map((d) => d.month), ...smapMonthly.map((d) => d.month)])
  ).sort();

  const lstByMonth = new Map(lstMonthly.map((d) => [d.month, d.value]));
  const smapByMonth = new Map(smapMonthly.map((d) => [d.month, d.value]));

  const lstSeries = months.map((m) => (lstByMonth.has(m) ? lstByMonth.get(m)! : null));
  const smapSeries = months.map((m) =>
    smapByMonth.has(m) ? smapByMonth.get(m)! : null
  );

  const option = {
    title: {
      text: "地表温度 LST · 土壤湿度 SMAP",
      textStyle: { fontSize: 14, fontWeight: 600, color: "#18181b" },
      left: 8,
      top: 4,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      valueFormatter: (v: number | null) =>
        v == null ? "—" : Number(v).toFixed(2),
    },
    legend: {
      data: ["LST (°C)", "土壤湿度 (m³/m³)"],
      top: 4,
      right: 8,
      textStyle: { fontSize: 11 },
    },
    grid: { left: 55, right: 60, top: 44, bottom: 36 },
    xAxis: {
      type: "category",
      data: months,
      axisLabel: { fontSize: 10, rotate: 45, hideOverlap: true },
    },
    yAxis: [
      {
        type: "value",
        name: "°C",
        nameTextStyle: { fontSize: 10 },
        axisLabel: { fontSize: 10 },
      },
      {
        type: "value",
        name: "m³/m³",
        nameTextStyle: { fontSize: 10 },
        axisLabel: { fontSize: 10, formatter: (v: number) => v.toFixed(2) },
        min: 0,
        max: 0.5,
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "LST (°C)",
        type: "line",
        data: lstSeries,
        connectNulls: true,
        smooth: true,
        symbol: "none",
        lineStyle: { width: 2, color: "#ef4444" },
        areaStyle: { color: "rgba(239, 68, 68, 0.06)" },
      },
      {
        name: "土壤湿度 (m³/m³)",
        type: "line",
        yAxisIndex: 1,
        data: smapSeries,
        connectNulls: true,
        smooth: true,
        symbol: "none",
        lineStyle: { width: 2, color: "#0ea5e9" },
        areaStyle: { color: "rgba(14, 165, 233, 0.10)" },
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
  value: number;
}

function aggregateMonthly(data: TimeseriesRecord[]): MonthlyAgg[] {
  const buckets = new Map<string, number[]>();
  for (const d of data) {
    if (!Number.isFinite(d.value)) continue;
    const month = d.time.slice(0, 7);
    (buckets.get(month) ?? buckets.set(month, []).get(month)!).push(d.value);
  }
  const out: MonthlyAgg[] = [];
  for (const [month, vs] of buckets) {
    out.push({
      month,
      value: vs.reduce((s, v) => s + v, 0) / vs.length,
    });
  }
  out.sort((a, b) => (a.month < b.month ? -1 : 1));
  return out;
}

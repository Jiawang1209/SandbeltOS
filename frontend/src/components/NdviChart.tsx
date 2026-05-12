"use client";

import ReactECharts from "echarts-for-react";
import type { ForecastPoint, TimeseriesRecord } from "@/lib/api";

interface NdviChartProps {
  ndviData: TimeseriesRecord[];
  eviData: TimeseriesRecord[];
  /**
   * Optional Prophet forecast — when present, an extra dashed line and
   * confidence band extend the NDVI series into the future. The first
   * forecast point is joined to the last historical NDVI point so the
   * eye reads a continuous trajectory.
   */
  forecast?: ForecastPoint[];
}

export default function NdviChart({ ndviData, eviData, forecast }: NdviChartProps) {
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

  // ---- Forecast overlay ----
  // Anchor the forecast line at the last historical NDVI sample so the
  // dashed extension appears continuous on the chart.
  const lastHistorical = ndviData.length > 0 ? ndviData[ndviData.length - 1] : null;
  const forecastLine: Array<[string, number]> = forecast
    ? [
        ...(lastHistorical
          ? ([[lastHistorical.time, lastHistorical.value]] as Array<[string, number]>)
          : []),
        ...forecast.map((p) => [p.date, p.yhat] as [string, number]),
      ]
    : [];
  // Confidence band is rendered as two stacked series: lower (transparent)
  // + (upper - lower) as a translucent area on top. ECharts renders
  // stacked area between the two, giving us a band.
  const forecastLowerStack: Array<[string, number]> = forecast
    ? forecast.map((p) => [p.date, p.yhat_lower])
    : [];
  const forecastBandStack: Array<[string, number]> = forecast
    ? forecast.map((p) => [p.date, Math.max(0, p.yhat_upper - p.yhat_lower)])
    : [];

  const baseLegend = ["NDVI", "EVI", "NDVI 年均趋势"];
  const legend = forecast && forecast.length > 0
    ? [...baseLegend, "NDVI 预测", "置信区间"]
    : baseLegend;

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
        const visible = params.filter(
          (p) =>
            p.seriesName !== "__forecast_lower" && p.seriesName !== "置信区间"
        );
        const lines = visible.map(
          (p) => `${p.marker} ${p.seriesName}: ${p.value[1].toFixed(4)}`
        );
        return `${date}<br/>${lines.join("<br/>")}`;
      },
    },
    legend: {
      data: legend,
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
      // Lower bound (invisible) — anchors the confidence band stack.
      ...(forecast && forecast.length > 0
        ? [
            {
              name: "__forecast_lower",
              type: "line",
              stack: "forecast-band",
              data: forecastLowerStack,
              symbol: "none",
              lineStyle: { opacity: 0 },
              areaStyle: { opacity: 0 },
              showInLegend: false,
              tooltip: { show: false },
              z: 1,
            },
            {
              name: "置信区间",
              type: "line",
              stack: "forecast-band",
              data: forecastBandStack,
              symbol: "none",
              lineStyle: { opacity: 0 },
              areaStyle: { color: "rgba(34, 197, 94, 0.18)" },
              z: 1,
            },
            {
              name: "NDVI 预测",
              type: "line",
              data: forecastLine,
              smooth: true,
              symbol: "circle",
              symbolSize: 4,
              lineStyle: { width: 2, color: "#16a34a", type: "dashed" },
              itemStyle: { color: "#16a34a" },
              z: 4,
            },
          ]
        : []),
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

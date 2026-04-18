"use client";
import type { Metrics } from "@/lib/chat-types";

interface Props {
  metrics: Metrics | null | undefined;
}

const RISK_LABEL = ["", "低", "较低", "中", "高"];

export function MetricsPanel({ metrics }: Props) {
  if (!metrics) {
    return <div className="text-sm text-neutral-400">无实时数据</div>;
  }
  return (
    <dl className="grid grid-cols-2 gap-y-2 text-sm">
      <dt className="text-neutral-500">区域</dt>
      <dd>{metrics.region}</dd>
      <dt className="text-neutral-500">NDVI</dt>
      <dd className="font-mono">{metrics.ndvi?.toFixed(2)}</dd>
      <dt className="text-neutral-500">FVC</dt>
      <dd className="font-mono">{metrics.fvc}%</dd>
      <dt className="text-neutral-500">风险等级</dt>
      <dd>
        {metrics.risk_level} / 4 ({RISK_LABEL[metrics.risk_level] ?? "?"})
      </dd>
      <dt className="text-neutral-500">风速</dt>
      <dd className="font-mono">{metrics.wind_speed?.toFixed(1)} m/s</dd>
      <dt className="text-neutral-500">土壤湿度</dt>
      <dd className="font-mono">{metrics.soil_moisture}%</dd>
      {metrics.last_alert && (
        <>
          <dt className="text-neutral-500">最近告警</dt>
          <dd className="text-red-600">{metrics.last_alert.message}</dd>
        </>
      )}
    </dl>
  );
}

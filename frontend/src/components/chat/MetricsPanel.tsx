"use client";
import type { Metrics } from "@/lib/chat-types";

interface Props {
  metrics: Metrics | null | undefined;
}

const RISK_LABEL = ["", "低", "较低", "中", "高"];

function riskTone(level: number): string {
  if (level >= 4) return "text-[var(--accent-ember)]";
  if (level === 3) return "text-[var(--accent-gold)]";
  return "text-[var(--forest-800)]";
}

export function MetricsPanel({ metrics }: Props) {
  if (!metrics) {
    return (
      <div className="rounded-md border border-dashed border-[var(--line)] px-3 py-6 text-center text-xs text-[var(--ink-soft)]">
        无实时数据
      </div>
    );
  }
  const label = RISK_LABEL[metrics.risk_level] ?? "?";
  return (
    <div className="rounded-md border border-[var(--line)] bg-[var(--surface)] p-3 text-sm">
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-[13px] font-medium text-[var(--ink-strong)]">
          {metrics.region}
        </span>
        <span className="num text-[11px] text-[var(--ink-soft)]">
          {metrics.timestamp?.slice(0, 10)}
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-[12.5px]">
        <Metric label="NDVI" value={metrics.ndvi?.toFixed(2)} />
        <Metric label="FVC" value={`${metrics.fvc}%`} />
        <Metric
          label="风险等级"
          value={
            <span className={`font-semibold ${riskTone(metrics.risk_level)}`}>
              {metrics.risk_level}/4 · {label}
            </span>
          }
        />
        <Metric label="风速" value={`${metrics.wind_speed?.toFixed(1)} m/s`} />
        <Metric
          label="土壤湿度"
          value={`${metrics.soil_moisture}%`}
          span={2}
        />
      </dl>

      {metrics.last_alert && (
        <div className="mt-3 rounded-md border border-[var(--accent-ember)]/20 bg-[var(--accent-ember)]/5 px-2.5 py-2 text-[11.5px]">
          <div className="mb-0.5 flex items-center gap-1.5 text-[10px] uppercase tracking-[0.12em] text-[var(--accent-ember)]">
            <svg viewBox="0 0 20 20" className="h-3 w-3" fill="currentColor">
              <path d="M10 2l8 14H2L10 2zm0 5v4m0 2v.01" stroke="white" strokeWidth="1.4" fill="currentColor" />
            </svg>
            最近告警
          </div>
          <div className="text-[var(--ink-strong)]">
            {metrics.last_alert.message}
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  span,
}: {
  label: string;
  value: React.ReactNode;
  span?: number;
}) {
  return (
    <div className={span === 2 ? "col-span-2" : ""}>
      <dt className="text-[10px] uppercase tracking-[0.14em] text-[var(--ink-soft)]">
        {label}
      </dt>
      <dd className="num mt-0.5 text-[var(--ink-strong)]">{value}</dd>
    </div>
  );
}

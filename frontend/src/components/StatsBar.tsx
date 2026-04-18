import { RISK_LEVEL_COLORS, RISK_LEVEL_LABELS } from "@/lib/api";

export interface StatsBarProps {
  regionCount: number;
  totalAreaKm2: number;
  yearsSpan: { from: number; to: number } | null;
  latestRiskLevel: number | null;
  datasetsCount: number;
}

export default function StatsBar({
  regionCount,
  totalAreaKm2,
  yearsSpan,
  latestRiskLevel,
  datasetsCount,
}: StatsBarProps) {
  const items = [
    {
      value: regionCount.toString(),
      unit: "片重点沙地",
      label: "监测区域",
      sub: "Sandy Lands",
    },
    {
      value: totalAreaKm2.toLocaleString("en-US"),
      unit: "km²",
      label: "监测面积",
      sub: "Coverage Area",
    },
    {
      value: yearsSpan
        ? (yearsSpan.to - yearsSpan.from + 1).toString()
        : "—",
      unit: "年连续观测",
      label: "时序跨度",
      sub: yearsSpan ? `${yearsSpan.from}–${yearsSpan.to}` : "Time-series",
    },
    {
      value: datasetsCount.toString(),
      unit: "套核心数据",
      label: "融合数据集",
      sub: "MODIS · Landsat · ERA5 · WorldCover",
    },
    {
      value: latestRiskLevel != null ? `L${latestRiskLevel}` : "—",
      unit:
        latestRiskLevel != null && RISK_LEVEL_LABELS[latestRiskLevel]
          ? RISK_LEVEL_LABELS[latestRiskLevel]
          : "—",
      label: "当前风险",
      sub: "Latest Risk Level",
      color: latestRiskLevel != null ? RISK_LEVEL_COLORS[latestRiskLevel] : undefined,
    },
  ];

  return (
    <section
      className="bg-topo relative overflow-hidden border-b border-[var(--line)]"
      style={{ background: "linear-gradient(180deg, var(--surface-warm) 0%, var(--background) 100%)" }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "repeating-linear-gradient(135deg, var(--forest-900) 0 1px, transparent 1px 22px)",
        }}
      />
      <div className="mx-auto max-w-[1600px] px-6 py-5">
        <div className="mb-3 flex items-baseline justify-between">
          <div className="flex items-center gap-2">
            <span className="divider-stripe" />
            <span className="eyebrow">核心指标概览 · Platform at a Glance</span>
          </div>
          <span className="text-[10px] text-[var(--ink-soft)] tracking-[0.18em] uppercase">
            Realtime / Three-North Shelterbelt
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-[var(--line)]">
          {items.map((it, i) => (
            <div key={i} className={`${i === 0 ? "" : "pl-6"} ${i === items.length - 1 ? "" : "pr-6"}`}>
              <div
                className="display-num text-[38px] leading-none text-[var(--ink-strong)]"
                style={it.color ? { color: it.color } : undefined}
              >
                {it.value}
                <span className="ml-1.5 text-[13px] font-normal tracking-wide text-[var(--ink-muted)]">
                  {it.unit}
                </span>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <span className="h-[2px] w-4" style={{ background: "var(--forest-700)" }} />
                <span className="text-[12px] font-medium text-[var(--ink-strong)]">{it.label}</span>
              </div>
              <div className="mt-0.5 text-[10.5px] tracking-[0.1em] text-[var(--ink-soft)]">
                {it.sub}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

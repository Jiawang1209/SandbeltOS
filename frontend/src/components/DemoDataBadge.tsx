"use client";

/**
 * Floating "演示数据" badge — flagged on any view that mixes synthetic
 * source data into a model output (forecast, scenario). Removed once
 * the upstream pipeline switches to real GEE / ERA5 ingestion for the
 * region in question.
 *
 * Anchors to the *parent* (the consuming card must be `position: relative`).
 */
interface DemoDataBadgeProps {
  className?: string;
  title?: string;
}

export default function DemoDataBadge({
  className,
  title = "本视图融合合成数据,真实 GEE / ERA5 数据接入后会重新校准。",
}: DemoDataBadgeProps) {
  return (
    <span
      title={title}
      className={
        "pointer-events-auto inline-flex select-none items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-700 shadow-sm " +
        (className ?? "")
      }
    >
      <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
      演示数据
    </span>
  );
}

"use client";

/**
 * Floating "演示数据" badge — gated by NEXT_PUBLIC_DEMO_MODE at build
 * time. Hidden by default since the GEE / ERA5 / SMAP pipelines now
 * ingest real data; set NEXT_PUBLIC_DEMO_MODE=true in `.env` (and
 * rebuild the frontend) to bring the badge back as a fallback, e.g.
 * during synthetic-data demos or model-calibration walkthroughs.
 *
 * Call sites stay unchanged: this component always renders null when
 * the env var is off, so wrapping JSX and conditional logic at the
 * consumer remain intact.
 *
 * Anchors to the *parent* (the consuming card must be `position: relative`).
 */
interface DemoDataBadgeProps {
  className?: string;
  title?: string;
}

const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export default function DemoDataBadge({
  className,
  title = "本视图融合合成数据 / 模型外推。设置 NEXT_PUBLIC_DEMO_MODE=true 才会显示此角标。",
}: DemoDataBadgeProps) {
  if (!DEMO_MODE) return null;
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

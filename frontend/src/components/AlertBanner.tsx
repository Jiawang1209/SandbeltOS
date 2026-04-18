"use client";

import type { AlertRecord } from "@/lib/api";

interface AlertBannerProps {
  alerts: AlertRecord[];
}

export default function AlertBanner({ alerts }: AlertBannerProps) {
  if (alerts.length === 0) return null;

  const critical = alerts.filter((a) => a.severity === "critical").length;
  const high = alerts.filter((a) => a.severity === "high").length;
  const latest = alerts[0];

  const tone =
    critical > 0
      ? { bg: "bg-red-600", label: "极高风险预警" }
      : { bg: "bg-orange-500", label: "高风险预警" };

  return (
    <div
      className={`${tone.bg} flex items-center gap-3 px-5 py-2 text-sm text-white`}
      role="alert"
    >
      <span className="font-semibold tracking-tight">{tone.label}</span>
      <span className="opacity-90">
        {critical > 0 && <>极高 {critical} 条</>}
        {critical > 0 && high > 0 && " · "}
        {high > 0 && <>高 {high} 条</>}
      </span>
      <span className="flex-1 truncate opacity-80">
        最近：{latest.message}
      </span>
    </div>
  );
}

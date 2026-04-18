"use client";
import type { Source } from "@/lib/chat-types";

interface Props {
  sources: Source[];
  highlightId?: number | null;
}

export function SourcesPanel({ sources, highlightId }: Props) {
  if (sources.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-[var(--line)] px-3 py-6 text-center text-xs text-[var(--ink-soft)]">
        暂无引用
      </div>
    );
  }
  return (
    <ol className="space-y-2">
      {sources.map((s) => {
        const active = highlightId === s.id;
        return (
          <li
            key={s.id}
            id={`source-${s.id}`}
            className={`rounded-md border px-3 py-2.5 text-sm transition ${
              active
                ? "border-[var(--forest-600)] bg-[var(--forest-50)] shadow-[0_0_0_3px_rgba(85,176,130,0.12)]"
                : "border-[var(--line)] bg-[var(--surface)] hover:border-[var(--line-strong)]"
            }`}
          >
            <div className="flex items-start gap-2">
              <span
                className={`mt-0.5 inline-flex h-5 min-w-[22px] items-center justify-center rounded-md px-1.5 text-[11px] font-semibold ${
                  active
                    ? "bg-[var(--forest-700)] text-white"
                    : "bg-[var(--forest-100)] text-[var(--forest-900)]"
                }`}
              >
                {s.id}
              </span>
              <span className="flex-1 text-[13px] font-medium leading-snug text-[var(--ink-strong)]">
                {s.title}
              </span>
            </div>
            <div className="mt-1.5 flex items-center gap-1.5 pl-[30px] text-[11px] text-[var(--ink-soft)]">
              <span className="truncate">{s.source}</span>
              <span className="text-[var(--line-strong)]">·</span>
              <span>p.{s.page}</span>
              <span className="text-[var(--line-strong)]">·</span>
              <span className="num">{s.score.toFixed(2)}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

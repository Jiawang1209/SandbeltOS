"use client";
import type { Source } from "@/lib/chat-types";

interface Props {
  sources: Source[];
  highlightId?: number | null;
}

export function SourcesPanel({ sources, highlightId }: Props) {
  if (sources.length === 0) {
    return <div className="text-sm text-neutral-400">暂无引用</div>;
  }
  return (
    <ol className="space-y-3">
      {sources.map((s) => (
        <li
          key={s.id}
          id={`source-${s.id}`}
          className={`rounded border p-3 text-sm transition ${
            highlightId === s.id
              ? "border-blue-400 bg-blue-50"
              : "border-neutral-200"
          }`}
        >
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xs text-blue-700">[{s.id}]</span>
            <span className="font-medium text-neutral-900">{s.title}</span>
          </div>
          <div className="mt-1 text-xs text-neutral-500">
            {s.source} · page {s.page} · score {s.score.toFixed(2)}
          </div>
        </li>
      ))}
    </ol>
  );
}

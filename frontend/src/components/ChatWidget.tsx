"use client";
import { useState } from "react";

import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { useChat } from "@/hooks/useChat";
import type { Metrics, Source } from "@/lib/chat-types";

interface Props {
  regionHint?: string | null;
}

export function ChatWidget({ regionHint }: Props) {
  const [open, setOpen] = useState(false);
  const { messages, streaming, ask } = useChat();

  const lastAssistant = [...messages]
    .reverse()
    .find((m) => m.role === "assistant");
  const sources: Source[] = lastAssistant?.sources ?? [];
  const metrics: Metrics | null | undefined = lastAssistant?.metrics;

  if (!open) {
    return (
      <button
        aria-label="打开 SandbeltOS 问答"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg hover:bg-blue-700"
      >
        💬
      </button>
    );
  }

  return (
    <div
      className="fixed bottom-6 right-6 z-50 flex w-[400px] flex-col overflow-hidden rounded-lg border border-neutral-300 bg-white shadow-2xl"
      style={{ height: "60vh" }}
    >
      <header className="flex items-center justify-between border-b border-neutral-200 px-3 py-2">
        <span className="text-sm font-medium">SandbeltOS Copilot</span>
        <div className="flex gap-1">
          <a
            href="/chat"
            aria-label="在全屏模式打开"
            className="rounded p-1 text-neutral-500 hover:bg-neutral-100"
          >
            ⤢
          </a>
          <button
            aria-label="关闭"
            onClick={() => setOpen(false)}
            className="rounded p-1 text-neutral-500 hover:bg-neutral-100"
          >
            ✕
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-3">
        {messages.length === 0 && (
          <div className="py-4 text-xs text-neutral-500">
            💡 试问：
            <ul className="mt-2 space-y-1">
              <li>
                <button
                  onClick={() => ask("现在风险怎么样？", regionHint)}
                  className="text-blue-600 hover:underline"
                >
                  现在风险怎么样？
                </button>
              </li>
              <li>
                <button
                  onClick={() => ask("RWEQ 公式是什么？", regionHint)}
                  className="text-blue-600 hover:underline"
                >
                  RWEQ 公式是什么？
                </button>
              </li>
            </ul>
          </div>
        )}
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
        {sources.length > 0 && (
          <div className="flex flex-wrap gap-1 border-t border-neutral-100 py-2">
            {sources.map((s) => (
              <span
                key={s.id}
                title={`${s.title} · p.${s.page}`}
                className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700"
              >
                [{s.id}] {s.source.slice(0, 24)}…
              </span>
            ))}
          </div>
        )}
        {metrics && (
          <div className="border-t border-neutral-100 py-2 text-xs text-neutral-600">
            📊 {metrics.region}: NDVI {metrics.ndvi?.toFixed(2)}, 风险{" "}
            {metrics.risk_level}/4
          </div>
        )}
      </div>

      <div className="border-t border-neutral-200 p-2">
        <ChatInput onSend={(q) => ask(q, regionHint)} disabled={streaming} />
      </div>
    </div>
  );
}

"use client";
import { useState } from "react";

import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { EmptyState } from "@/components/chat/EmptyState";
import { MetricsPanel } from "@/components/chat/MetricsPanel";
import { SourcesPanel } from "@/components/chat/SourcesPanel";
import { useChat } from "@/hooks/useChat";

export default function ChatPage() {
  const { messages, streaming, ask, reset } = useChat();
  const [highlightId, setHighlightId] = useState<number | null>(null);

  const lastAssistant = [...messages]
    .reverse()
    .find((m) => m.role === "assistant");
  const sources = lastAssistant?.sources ?? [];
  const metrics = lastAssistant?.metrics ?? null;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-neutral-200 px-6 py-3">
        <h1 className="text-sm font-medium">SandbeltOS 智慧问答</h1>
        <button
          onClick={reset}
          disabled={streaming || messages.length === 0}
          className="rounded border border-neutral-300 px-3 py-1 text-xs text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
        >
          新对话
        </button>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <main className="flex flex-1 flex-col">
          <div className="flex-1 overflow-y-auto px-6">
            {messages.length === 0 ? (
              <EmptyState onPick={ask} />
            ) : (
              <div className="mx-auto max-w-3xl divide-y divide-neutral-200">
                {messages.map((m) => (
                  <ChatMessage
                    key={m.id}
                    message={m}
                    onCitationClick={setHighlightId}
                  />
                ))}
              </div>
            )}
          </div>
          <div className="mx-auto w-full max-w-3xl px-6 py-4">
            <ChatInput onSend={ask} disabled={streaming} />
          </div>
        </main>

        <aside className="w-[320px] overflow-y-auto border-l border-neutral-200 bg-neutral-50 p-4">
          <section className="mb-6">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
              引用来源
            </h2>
            <SourcesPanel sources={sources} highlightId={highlightId} />
          </section>
          <section>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
              实时指标
            </h2>
            <MetricsPanel metrics={metrics} />
          </section>
        </aside>
      </div>
    </div>
  );
}

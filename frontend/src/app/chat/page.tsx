"use client";
import { useEffect, useMemo, useRef, useState } from "react";

import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ConversationsSidebar } from "@/components/chat/ConversationsSidebar";
import { EmptyState } from "@/components/chat/EmptyState";
import { MetricsPanel } from "@/components/chat/MetricsPanel";
import { SourcesPanel } from "@/components/chat/SourcesPanel";
import { useChat } from "@/hooks/useChat";
import { useConversations } from "@/hooks/useConversations";

export default function ChatPage() {
  const {
    conversations,
    active,
    activeId,
    updateActiveMessages,
    create,
    select,
    remove,
  } = useConversations();

  const messages = active?.messages ?? [];

  const { streaming, ask, stop } = useChat({
    messages,
    updateMessages: updateActiveMessages,
  });

  const [highlightId, setHighlightId] = useState<number | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);

  const lastAssistant = useMemo(
    () => [...messages].reverse().find((m) => m.role === "assistant"),
    [messages],
  );
  const sources = lastAssistant?.sources ?? [];
  const metrics = lastAssistant?.metrics ?? null;

  const scrollRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const hasData = sources.length > 0 || metrics;

  return (
    <div className="flex h-screen flex-col bg-[var(--background)]">
      <div className="header-accent" />
      <div className="flex flex-1 overflow-hidden">
        <ConversationsSidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={select}
          onCreate={create}
          onRemove={remove}
        />

        <main className="relative flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-[var(--line)] bg-[var(--surface)] px-6 py-3">
            <div className="flex items-baseline gap-3">
              <h1 className="font-serif text-[15px] font-semibold tracking-tight text-[var(--ink-strong)]">
                {active?.title ?? "智慧问答"}
              </h1>
              <span className="text-[11px] text-[var(--ink-soft)]">
                RAG · bge-m3 + 磐石大模型
              </span>
            </div>
            <button
              onClick={() => setPanelOpen((v) => !v)}
              className="flex items-center gap-1.5 rounded-md border border-[var(--line)] px-2.5 py-1 text-[11px] text-[var(--ink-muted)] transition hover:border-[var(--forest-600)] hover:text-[var(--forest-700)]"
              aria-label={panelOpen ? "收起右侧" : "展开右侧"}
            >
              <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                {panelOpen ? (
                  <path d="M12 4l5 6-5 6M3 4h5v12H3" />
                ) : (
                  <path d="M8 4l-5 6 5 6M17 4h-5v12h5" />
                )}
              </svg>
              {panelOpen ? "收起" : "展开"}依据
            </button>
          </header>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-6">
            {messages.length === 0 ? (
              <EmptyState onPick={ask} />
            ) : (
              <div className="mx-auto flex max-w-3xl flex-col pb-6">
                {messages.map((m) => (
                  <ChatMessage
                    key={m.id}
                    message={m}
                    onCitationClick={(id) => {
                      setHighlightId(id);
                      if (!panelOpen) setPanelOpen(true);
                      setTimeout(() => {
                        document
                          .getElementById(`source-${id}`)
                          ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
                      }, 50);
                    }}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="border-t border-[var(--line)] bg-[var(--surface)] px-6 py-4">
            <div className="mx-auto w-full max-w-3xl">
              <ChatInput
                onSend={ask}
                onStop={stop}
                disabled={streaming}
                streaming={streaming}
              />
              <p className="mt-2 text-center text-[10.5px] text-[var(--ink-soft)]">
                回答基于检索文献 + 实时传感器数据，生成内容仅供研究参考，请以原始资料为准
              </p>
            </div>
          </div>
        </main>

        {panelOpen && (
          <aside className="flex w-[340px] flex-col overflow-hidden border-l border-[var(--line)] bg-[var(--surface-sunk)]">
            <div className="flex-1 space-y-6 overflow-y-auto px-4 py-5">
              <section>
                <div className="eyebrow mb-2.5">引用来源</div>
                <SourcesPanel sources={sources} highlightId={highlightId} />
              </section>
              <section>
                <div className="eyebrow mb-2.5">实时指标</div>
                <MetricsPanel metrics={metrics} />
              </section>
              {!hasData && messages.length === 0 && (
                <div className="text-[11.5px] leading-relaxed text-[var(--ink-soft)]">
                  提问后，回答依据的文献与当前区域的实时监测指标会出现在此侧。
                </div>
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}

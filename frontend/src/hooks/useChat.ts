"use client";
import { useCallback, useRef, useState } from "react";

import type { ChatMessage, Metrics, Source } from "@/lib/chat-types";
import { parseSSE } from "@/lib/sse";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const updateLast = useCallback((patch: Partial<ChatMessage>) => {
    setMessages((prev) => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      return [
        ...prev.slice(0, -1),
        { ...last, ...patch, content: patch.content ?? last.content },
      ];
    });
  }, []);

  const appendToken = useCallback((delta: string) => {
    setMessages((prev) => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      return [...prev.slice(0, -1), { ...last, content: last.content + delta }];
    });
  }, []);

  const ask = useCallback(
    async (question: string, regionHint?: string | null) => {
      const now = Date.now().toString();
      setMessages((prev) => [
        ...prev,
        { id: `u-${now}`, role: "user", content: question },
        {
          id: `a-${now}`,
          role: "assistant",
          content: "",
          sources: [],
          metrics: null,
          streaming: true,
        },
      ]);
      setStreaming(true);

      const ac = new AbortController();
      abortRef.current = ac;

      try {
        const res = await fetch(`${API_BASE}/api/v1/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question,
            region_hint: regionHint ?? null,
          }),
          signal: ac.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        for await (const evt of parseSSE(res)) {
          if (evt.event === "sources") {
            updateLast({ sources: JSON.parse(evt.data) as Source[] });
          } else if (evt.event === "metrics") {
            updateLast({ metrics: JSON.parse(evt.data) as Metrics });
          } else if (evt.event === "token") {
            appendToken(JSON.parse(evt.data) as string);
          } else if (evt.event === "error") {
            const { message } = JSON.parse(evt.data) as { message: string };
            updateLast({ error: message });
          } else if (evt.event === "done") {
            updateLast({ streaming: false });
          }
        }
      } catch (err: unknown) {
        updateLast({
          streaming: false,
          error: (err as Error).message,
        });
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [updateLast, appendToken],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    setMessages([]);
    setStreaming(false);
  }, []);

  return { messages, streaming, ask, stop, reset };
}

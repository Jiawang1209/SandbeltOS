"use client";
import { useCallback, useRef, useState } from "react";

import type { ChatMessage, Metrics, Source } from "@/lib/chat-types";
import { parseSSE } from "@/lib/sse";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ExternalState = {
  messages: ChatMessage[];
  updateMessages: (updater: (prev: ChatMessage[]) => ChatMessage[]) => void;
};

// Accept optional externally-controlled state so the /chat page can store
// messages inside a conversation (localStorage-backed). When omitted, the
// hook manages its own in-memory state — which is what ChatWidget does.
export function useChat(external?: ExternalState) {
  const [internalMessages, setInternalMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const messages = external?.messages ?? internalMessages;
  const updateMessages = useCallback(
    (updater: (prev: ChatMessage[]) => ChatMessage[]) => {
      if (external) external.updateMessages(updater);
      else setInternalMessages(updater);
    },
    [external],
  );

  const updateLast = useCallback(
    (patch: Partial<ChatMessage>) => {
      updateMessages((prev) => {
        if (prev.length === 0) return prev;
        const last = prev[prev.length - 1];
        return [
          ...prev.slice(0, -1),
          { ...last, ...patch, content: patch.content ?? last.content },
        ];
      });
    },
    [updateMessages],
  );

  const appendToken = useCallback(
    (delta: string) => {
      updateMessages((prev) => {
        if (prev.length === 0) return prev;
        const last = prev[prev.length - 1];
        return [
          ...prev.slice(0, -1),
          { ...last, content: last.content + delta },
        ];
      });
    },
    [updateMessages],
  );

  const ask = useCallback(
    async (question: string, regionHint?: string | null) => {
      const now = Date.now().toString();
      updateMessages((prev) => [
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
            updateLast({ error: message, streaming: false });
          } else if (evt.event === "done") {
            updateLast({ streaming: false });
          }
        }
      } catch (err: unknown) {
        const message =
          err instanceof DOMException && err.name === "AbortError"
            ? "已停止"
            : (err as Error).message;
        updateLast({ streaming: false, error: message });
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [updateMessages, updateLast, appendToken],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    updateMessages(() => []);
    setStreaming(false);
  }, [updateMessages]);

  return { messages, streaming, ask, stop, reset };
}

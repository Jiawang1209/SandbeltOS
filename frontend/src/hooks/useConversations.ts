"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ChatMessage } from "@/lib/chat-types";
import {
  emptyConversation,
  deriveTitle,
  loadConversations,
  saveConversations,
  type Conversation,
} from "@/lib/conversations";

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const hydrated = useRef(false);

  // Hydrate from localStorage on mount. Creating a fresh conversation when
  // the store is empty keeps the UI usable on first load.
  useEffect(() => {
    const stored = loadConversations();
    if (stored.length > 0) {
      setConversations(stored);
      setActiveId(stored[0].id);
    } else {
      const fresh = emptyConversation();
      setConversations([fresh]);
      setActiveId(fresh.id);
    }
    hydrated.current = true;
  }, []);

  // Persist after hydration so we don't overwrite storage with the empty
  // initial state during the first render pass.
  useEffect(() => {
    if (!hydrated.current) return;
    saveConversations(conversations);
  }, [conversations]);

  const active = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? null,
    [conversations, activeId],
  );

  const updateActiveMessages = useCallback(
    (updater: (prev: ChatMessage[]) => ChatMessage[]) => {
      setConversations((prev) => {
        if (prev.length === 0) return prev;
        const idx = prev.findIndex((c) => c.id === activeId);
        if (idx < 0) return prev;
        const current = prev[idx];
        const nextMessages = updater(current.messages);
        if (nextMessages === current.messages) return prev;
        const next: Conversation = {
          ...current,
          messages: nextMessages,
          title:
            current.title === "新对话" || current.messages.length === 0
              ? deriveTitle(nextMessages)
              : current.title,
          updatedAt: Date.now(),
        };
        const copy = [...prev];
        copy[idx] = next;
        return copy;
      });
    },
    [activeId],
  );

  const create = useCallback(() => {
    const fresh = emptyConversation();
    setConversations((prev) => [fresh, ...prev]);
    setActiveId(fresh.id);
  }, []);

  const select = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const remove = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        if (next.length === 0) {
          const fresh = emptyConversation();
          setActiveId(fresh.id);
          return [fresh];
        }
        if (id === activeId) {
          setActiveId(next[0].id);
        }
        return next;
      });
    },
    [activeId],
  );

  const rename = useCallback((id: string, title: string) => {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === id ? { ...c, title: title.trim() || c.title } : c,
      ),
    );
  }, []);

  return {
    conversations,
    active,
    activeId,
    updateActiveMessages,
    create,
    select,
    remove,
    rename,
  };
}

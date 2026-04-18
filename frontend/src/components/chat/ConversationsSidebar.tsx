"use client";
import { useMemo } from "react";

import type { Conversation } from "@/lib/conversations";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onRemove: (id: string) => void;
}

function groupByRecency(conversations: Conversation[]) {
  const now = Date.now();
  const day = 24 * 60 * 60 * 1000;
  const today: Conversation[] = [];
  const week: Conversation[] = [];
  const older: Conversation[] = [];
  for (const c of [...conversations].sort((a, b) => b.updatedAt - a.updatedAt)) {
    const diff = now - c.updatedAt;
    if (diff < day) today.push(c);
    else if (diff < 7 * day) week.push(c);
    else older.push(c);
  }
  return { today, week, older };
}

export function ConversationsSidebar({
  conversations,
  activeId,
  onSelect,
  onCreate,
  onRemove,
}: Props) {
  const groups = useMemo(() => groupByRecency(conversations), [conversations]);

  return (
    <aside className="flex h-full w-[260px] flex-col border-r border-[var(--line)] bg-[var(--surface-sunk)]">
      <div className="px-3 pt-4 pb-3">
        <button
          onClick={onCreate}
          className="group flex w-full items-center gap-2 rounded-lg border border-[var(--line-strong)] bg-[var(--surface)] px-3 py-2.5 text-sm font-medium text-[var(--ink-strong)] shadow-sm transition hover:border-[var(--forest-700)] hover:text-[var(--forest-700)]"
        >
          <svg
            viewBox="0 0 20 20"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <path d="M10 4v12M4 10h12" />
          </svg>
          新对话
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {conversations.length === 0 ? (
          <div className="mt-8 px-3 text-xs text-[var(--ink-soft)]">
            暂无对话
          </div>
        ) : (
          <>
            <Group label="今日" items={groups.today} activeId={activeId} onSelect={onSelect} onRemove={onRemove} />
            <Group label="本周" items={groups.week} activeId={activeId} onSelect={onSelect} onRemove={onRemove} />
            <Group label="更早" items={groups.older} activeId={activeId} onSelect={onSelect} onRemove={onRemove} />
          </>
        )}
      </div>

      <div className="border-t border-[var(--line)] px-4 py-3 text-[10px] leading-snug text-[var(--ink-soft)]">
        <div className="font-medium text-[var(--ink-muted)]">SandbeltOS</div>
        <div className="mt-0.5 tracking-[0.14em] uppercase">
          Phase 4 · RAG Copilot
        </div>
      </div>
    </aside>
  );
}

interface GroupProps {
  label: string;
  items: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
}

function Group({ label, items, activeId, onSelect, onRemove }: GroupProps) {
  if (items.length === 0) return null;
  return (
    <div className="mb-2">
      <div className="px-3 pt-3 pb-1 text-[10px] font-medium uppercase tracking-[0.18em] text-[var(--ink-soft)]">
        {label}
      </div>
      <ul>
        {items.map((c) => (
          <Row
            key={c.id}
            conversation={c}
            active={c.id === activeId}
            onSelect={onSelect}
            onRemove={onRemove}
          />
        ))}
      </ul>
    </div>
  );
}

interface RowProps {
  conversation: Conversation;
  active: boolean;
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
}

function Row({ conversation, active, onSelect, onRemove }: RowProps) {
  return (
    <li>
      <div
        className={`group relative flex items-center rounded-md px-3 py-2 text-sm transition ${
          active
            ? "bg-[var(--forest-100)] text-[var(--forest-900)]"
            : "text-[var(--ink)] hover:bg-white/60"
        }`}
      >
        {active && (
          <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-[var(--forest-700)]" />
        )}
        <button
          onClick={() => onSelect(conversation.id)}
          className="flex-1 truncate pr-2 text-left"
          title={conversation.title}
        >
          {conversation.title}
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (confirm(`删除对话"${conversation.title}"？`)) {
              onRemove(conversation.id);
            }
          }}
          className="ml-1 hidden h-6 w-6 items-center justify-center rounded text-[var(--ink-soft)] hover:bg-[var(--surface-sunk)] hover:text-[var(--accent-ember)] group-hover:flex"
          aria-label="删除对话"
        >
          <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M5 6h10M8 6V4h4v2M7 6v10h6V6" />
          </svg>
        </button>
      </div>
    </li>
  );
}

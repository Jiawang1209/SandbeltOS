"use client";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

interface Props {
  onSend: (text: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  streaming?: boolean;
}

export function ChatInput({ onSend, onStop, disabled, streaming }: Props) {
  const [value, setValue] = useState("");
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "0px";
    const next = Math.min(el.scrollHeight, 200);
    el.style.height = `${next}px`;
  }, [value]);

  function submit() {
    const v = value.trim();
    if (!v || disabled) return;
    onSend(v);
    setValue("");
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="card-surface flex items-end gap-2 px-3 py-2 transition focus-within:border-[var(--forest-600)] focus-within:shadow-[0_1px_0_rgba(13,74,48,0.04),0_8px_24px_-14px_rgba(13,74,48,0.22)]">
      <textarea
        ref={taRef}
        value={value}
        disabled={disabled}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKey}
        rows={1}
        placeholder="问一个关于三北、科尔沁或浑善达克的问题…"
        className="flex-1 resize-none border-0 bg-transparent px-2 py-2 text-sm leading-6 text-[var(--ink-strong)] placeholder:text-[var(--ink-soft)] outline-none disabled:opacity-60"
        style={{ maxHeight: 200 }}
      />
      {streaming ? (
        <button
          type="button"
          onClick={onStop}
          className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--line-strong)] bg-[var(--surface-sunk)] px-3 text-xs font-medium text-[var(--ink-muted)] transition hover:border-[var(--accent-ember)] hover:text-[var(--accent-ember)]"
          aria-label="停止生成"
        >
          <svg viewBox="0 0 20 20" className="h-3 w-3" fill="currentColor">
            <rect x="5" y="5" width="10" height="10" rx="1.5" />
          </svg>
          停止
        </button>
      ) : (
        <button
          type="button"
          onClick={submit}
          disabled={!canSend}
          className="flex h-9 items-center gap-1.5 rounded-md bg-[var(--forest-700)] px-4 text-xs font-medium text-white transition hover:bg-[var(--forest-900)] disabled:bg-[var(--surface-sunk)] disabled:text-[var(--ink-soft)]"
          aria-label="发送"
        >
          发送
          <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 10h12M11 5l5 5-5 5" />
          </svg>
        </button>
      )}
    </div>
  );
}

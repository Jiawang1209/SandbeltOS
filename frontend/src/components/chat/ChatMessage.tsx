"use client";
import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatMessage as Msg } from "@/lib/chat-types";

interface Props {
  message: Msg;
  onCitationClick?: (sourceId: number) => void;
}

export function ChatMessage({ message, onCitationClick }: Props) {
  const isUser = message.role === "user";
  return (
    <div
      className={`flex gap-3 px-1 py-4 ${
        isUser ? "flex-row-reverse" : ""
      }`}
    >
      <Avatar role={message.role} />
      <div className={`flex max-w-[78%] flex-col ${isUser ? "items-end" : "items-start"}`}>
        <div className="mb-1 text-[11px] font-medium tracking-wide text-[var(--ink-soft)]">
          {isUser ? "用户" : "SandbeltOS"}
        </div>
        <div
          className={
            isUser
              ? "rounded-2xl rounded-tr-sm bg-[var(--forest-700)] px-4 py-2.5 text-sm leading-relaxed text-white shadow-sm"
              : "rounded-2xl rounded-tl-sm border border-[var(--line)] bg-[var(--surface)] px-4 py-3 text-sm leading-relaxed text-[var(--ink-strong)] shadow-[0_1px_0_rgba(13,74,48,0.04)]"
          }
        >
          {message.error ? (
            <div className="flex items-center gap-2 text-[var(--accent-ember)]">
              <svg viewBox="0 0 20 20" className="h-4 w-4 flex-shrink-0" fill="currentColor">
                <path d="M10 2l8 14H2L10 2zm0 5v4m0 2v.01" stroke="white" strokeWidth="1.5" fill="none" />
              </svg>
              {message.error}
            </div>
          ) : message.content ? (
            <div
              className={
                isUser
                  ? "prose prose-sm prose-invert max-w-none prose-p:my-1.5 prose-p:leading-relaxed"
                  : "prose prose-sm max-w-none prose-p:my-1.5 prose-p:leading-relaxed prose-a:text-[var(--forest-700)] prose-strong:text-[var(--forest-900)] prose-code:text-[var(--forest-800)]"
              }
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children, ...props }) => (
                    <p {...props}>{renderCitations(children, onCitationClick)}</p>
                  ),
                  li: ({ children, ...props }) => (
                    <li {...props}>{renderCitations(children, onCitationClick)}</li>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          ) : message.streaming ? (
            <TypingDots />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Avatar({ role }: { role: "user" | "assistant" }) {
  if (role === "user") {
    return (
      <div className="mt-6 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[var(--surface-sunk)] text-[10px] font-semibold text-[var(--ink-muted)]">
        用户
      </div>
    );
  }
  return (
    <div className="mt-6 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[var(--forest-700)] to-[var(--forest-900)] shadow-sm">
      <svg viewBox="0 0 24 24" className="h-4 w-4 text-white" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
        <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" />
        <path d="M9 12l2 2 4-4" strokeLinecap="round" />
      </svg>
    </div>
  );
}

function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--forest-600)] [animation-delay:0ms]" />
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--forest-600)] [animation-delay:160ms]" />
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--forest-600)] [animation-delay:320ms]" />
    </div>
  );
}

function renderCitations(
  nodes: ReactNode,
  onClick?: (id: number) => void,
): ReactNode {
  if (typeof nodes === "string") {
    const parts = nodes.split(/(\[\d+\])/g);
    return parts.map((p, i) => {
      const m = p.match(/^\[(\d+)\]$/);
      if (m && onClick) {
        const id = Number(m[1]);
        return (
          <button
            key={i}
            onClick={() => onClick(id)}
            className="mx-0.5 inline-flex h-5 min-w-[20px] items-center justify-center rounded-md bg-[var(--forest-100)] px-1.5 align-baseline text-[11px] font-semibold text-[var(--forest-900)] transition hover:bg-[var(--forest-500)] hover:text-white"
          >
            {id}
          </button>
        );
      }
      return <span key={i}>{p}</span>;
    });
  }
  if (Array.isArray(nodes)) {
    return nodes.map((n, i) => (
      <span key={i}>{renderCitations(n, onClick)}</span>
    ));
  }
  return nodes;
}

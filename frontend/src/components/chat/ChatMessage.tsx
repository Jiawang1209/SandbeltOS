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
    <div className={`py-4 ${isUser ? "text-neutral-800" : "text-neutral-900"}`}>
      <div className="mb-1 text-xs uppercase tracking-wide text-neutral-500">
        {isUser ? "你" : "SandbeltOS"}
      </div>
      {message.error ? (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          错误：{message.error}
        </div>
      ) : (
        <div className="prose prose-sm max-w-none">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children, ...props }) => (
                <p {...props}>{renderCitations(children, onCitationClick)}</p>
              ),
            }}
          >
            {message.content || (message.streaming ? "..." : "")}
          </ReactMarkdown>
        </div>
      )}
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
            className="mx-0.5 inline-flex h-5 items-center rounded-full bg-blue-100 px-2 text-xs font-medium text-blue-700 hover:bg-blue-200"
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

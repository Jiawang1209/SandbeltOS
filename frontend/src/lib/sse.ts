export type SSEEvent = {
  event: string;
  data: string;
};

/**
 * Parse a fetch Response body as an SSE stream.
 * Yields one SSEEvent per `event: ... \n data: ... \n\n` block.
 */
export async function* parseSSE(
  response: Response,
): AsyncGenerator<SSEEvent> {
  if (!response.body) throw new Error("Response body is null");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let nlnl: number;
      while ((nlnl = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, nlnl);
        buffer = buffer.slice(nlnl + 2);
        const event = parseBlock(block);
        if (event) yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function parseBlock(block: string): SSEEvent | null {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data && event === "message") return null;
  return { event, data };
}

"""Claude streaming wrapper.

Thin adapter over `anthropic.AsyncAnthropic.messages.stream` that exposes
an `async for` of text deltas — the shape the chat endpoint re-emits as
SSE `token` events. Client is lazily constructed so tests can import the
module without an API key.
"""
from __future__ import annotations

from typing import AsyncGenerator

from anthropic import AsyncAnthropic

from app.config import settings

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def stream_completion(prompt: str) -> AsyncGenerator[str, None]:
    """Yield text deltas from Claude streaming."""
    client = _get_client()
    async with client.messages.stream(
        model=settings.claude_model,
        max_tokens=settings.claude_max_tokens,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for delta in stream.text_stream:
            yield delta

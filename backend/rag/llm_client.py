"""OpenAI-compatible LLM streaming wrapper.

Points `AsyncOpenAI` at whatever `LLM_BASE_URL` is configured — tested
against CSTCloud uni-api (`https://uni-api.cstcloud.cn/v1`) serving
`qwen3:235b`, but any OpenAI-compatible endpoint (vLLM, DeepSeek, local
Ollama, etc.) works without code changes.

Contract: `stream_completion(prompt)` yields text deltas. The chat
endpoint re-emits each delta as an SSE `token` event.
"""
from __future__ import annotations

from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.config import settings

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY not configured")
        _client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    return _client


async def stream_completion(prompt: str) -> AsyncGenerator[str, None]:
    """Yield text deltas from the configured OpenAI-compatible endpoint."""
    client = _get_client()
    stream = await client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta

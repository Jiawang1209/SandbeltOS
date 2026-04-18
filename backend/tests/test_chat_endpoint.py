"""Tests for POST /api/v1/chat (SSE endpoint)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from rag.types import Chunk, QueryContext, SearchResult


@pytest.mark.asyncio
async def test_chat_endpoint_requires_question() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/chat", json={})
    assert resp.status_code == 422  # pydantic validation error


@pytest.mark.asyncio
async def test_chat_streams_sources_then_tokens_then_done() -> None:
    """SSE contract: sources → token* → done, with sources before first token."""
    fake_results = [
        SearchResult(
            chunk=Chunk(
                text="sample",
                source="s.pdf",
                title="T",
                category="papers_en",
                page=1,
                lang="en",
                region_hint=[],
                chunk_id="",
            ),
            score=0.9,
        )
    ]

    async def fake_stream(_prompt: str):
        yield "Hello"
        yield " world"

    with (
        patch("app.api.v1.chat.retriever.retrieve", return_value=fake_results),
        patch("app.api.v1.chat.query_router.parse",
              return_value=QueryContext(regions=[], intents=[], needs_live_data=False)),
        patch("app.api.v1.chat.stream_completion", side_effect=fake_stream),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream(
                "POST", "/api/v1/chat", json={"question": "hi"}
            ) as r:
                body = b""
                async for chunk in r.aiter_bytes():
                    body += chunk
        text = body.decode()

    idx_sources = text.find("event: sources")
    idx_token = text.find("event: token")
    idx_done = text.find("event: done")
    assert idx_sources != -1 and idx_token != -1 and idx_done != -1
    assert idx_sources < idx_token < idx_done

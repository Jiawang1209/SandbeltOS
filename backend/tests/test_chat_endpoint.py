"""Tests for POST /api/v1/chat (SSE endpoint)."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_chat_endpoint_requires_question() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/chat", json={})
    assert resp.status_code == 422  # pydantic validation error

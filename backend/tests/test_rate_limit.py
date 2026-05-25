"""Per-route rate-limit tests.

Verifies that the slowapi decorators on `/chat` and `/scenario` actually
fire 429 after the configured budget — not just that they import. Uses
the shared `app.limiter.limiter` reset between tests to avoid in-memory
state bleed across cases.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.limiter import limiter
from app.main import app
from rag.types import Chunk, QueryContext, SearchResult


@pytest.fixture(autouse=True)
def _reset_limiter_state():
    """slowapi tracks counters in-memory; reset before AND after each test
    so order-of-execution doesn't carry hits between cases."""
    limiter.reset()
    yield
    limiter.reset()


def _fake_chunk(text: str = "x") -> SearchResult:
    return SearchResult(
        chunk=Chunk(
            text=text, source="s.pdf", title="T", category="papers_en",
            page=1, lang="en", region_hint=[], chunk_id="",
        ),
        score=0.9,
    )


@pytest.mark.asyncio
async def test_chat_limit_returns_429_after_budget() -> None:
    """Exhaust chat_rate_limit and expect the (budget+1)th call to be 429.

    Uses the default budget from settings — if a future bump makes the
    default huge, this test gets slow; we'd then override per-test.
    """
    settings = get_settings()
    # Parse "20/minute" → 20. Defensive against the format changing.
    budget = int(settings.chat_rate_limit.split("/")[0])

    async def fake_stream(_prompt: str):
        yield "ok"

    with (
        patch("app.api.v1.chat.retriever.retrieve", return_value=[_fake_chunk()]),
        patch(
            "app.api.v1.chat.query_router.parse",
            return_value=QueryContext(regions=[], intents=[], needs_live_data=False),
        ),
        patch("app.api.v1.chat.stream_completion", side_effect=fake_stream),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            statuses = []
            for _ in range(budget + 1):
                r = await c.post("/api/v1/chat", json={"question": "hi"})
                # Drain the SSE body so the next request starts cleanly
                if r.status_code == 200:
                    async for _chunk in r.aiter_bytes():
                        pass
                statuses.append(r.status_code)

    assert statuses[-1] == 429, f"final status should be 429, got {statuses[-1]}"
    assert statuses.count(200) == budget, (
        f"expected {budget} successful calls, got {statuses.count(200)} "
        f"(statuses={statuses})"
    )


@pytest.mark.asyncio
async def test_scenario_limit_independent_from_chat() -> None:
    """Per-route limits track separate counters — exhausting /chat must
    not 429 /scenario."""
    chat_budget = int(get_settings().chat_rate_limit.split("/")[0])

    async def fake_stream(_prompt: str):
        yield "ok"

    with (
        patch("app.api.v1.chat.retriever.retrieve", return_value=[_fake_chunk()]),
        patch(
            "app.api.v1.chat.query_router.parse",
            return_value=QueryContext(regions=[], intents=[], needs_live_data=False),
        ),
        patch("app.api.v1.chat.stream_completion", side_effect=fake_stream),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # Exhaust /chat
            for _ in range(chat_budget + 1):
                r = await c.post("/api/v1/chat", json={"question": "hi"})
                if r.status_code == 200:
                    async for _b in r.aiter_bytes():
                        pass

            # /scenario should still be reachable. We don't need the call
            # to succeed end-to-end — just to NOT be 429. A 4xx/5xx from
            # DB/validation is fine and proves the limiter didn't reject.
            r = await c.post(
                "/api/v1/prediction/scenario",
                json={
                    "region_id": 1,
                    "species": "salix",
                    "additional_density_per_ha": 1000,
                    "years": 5,
                },
            )
    assert r.status_code != 429, "/scenario should not share /chat's limit bucket"


def test_limiter_is_enabled_by_default() -> None:
    """Smoke: shared limiter exists and is enabled when api_rate_limit is set."""
    assert limiter is not None
    assert limiter.enabled is True


def test_per_route_limits_have_sensible_defaults() -> None:
    """Defaults should be stricter than the global so an LLM/scenario
    burst can't cost real money before the global limit kicks in."""
    s = get_settings()
    global_n = int(s.api_rate_limit.split("/")[0])
    chat_n = int(s.chat_rate_limit.split("/")[0])
    scenario_n = int(s.scenario_rate_limit.split("/")[0])
    assert chat_n < global_n, f"chat ({chat_n}) should be < global ({global_n})"
    assert scenario_n < global_n, f"scenario ({scenario_n}) should be < global ({global_n})"

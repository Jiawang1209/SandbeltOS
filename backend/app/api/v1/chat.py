"""POST /api/v1/chat — SSE streaming RAG answer.

Event order guaranteed by the generator below:
    sources  → (metrics)? → token* → (error)? → done

Retrieval is sync (bge-m3 load), so we wrap in `asyncio.to_thread` and
kick off live-metrics fan-out in parallel. The client renders citations
and live data before the first token arrives.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services import query_router
from rag import live_metrics, retriever
from rag.claude_client import stream_completion
from rag.prompt_templates import build_prompt, build_sources_meta

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    region_hint: str | None = Field(default=None, description="horqin | hunshandake")


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    ctx = query_router.parse(req.question)
    region = req.region_hint or (ctx.regions[0] if ctx.regions else None)

    async def stream() -> AsyncGenerator[str, None]:
        retrieve_task = asyncio.create_task(
            asyncio.to_thread(retriever.retrieve, req.question, region, None, True)
        )
        metrics_task: asyncio.Task | None = None
        if ctx.needs_live_data and region:
            metrics_task = asyncio.create_task(live_metrics.fetch_snapshot(region))

        results = await retrieve_task
        metrics = await metrics_task if metrics_task else None

        yield _sse(
            "sources",
            json.dumps(build_sources_meta(results), ensure_ascii=False),
        )
        if metrics is not None:
            yield _sse("metrics", json.dumps(metrics, ensure_ascii=False, default=str))

        prompt = build_prompt(req.question, results, metrics)
        try:
            async for delta in stream_completion(prompt):
                yield _sse("token", json.dumps(delta, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001 — surface to client as SSE error event
            yield _sse("error", json.dumps({"message": str(e)}, ensure_ascii=False))
        finally:
            yield _sse("done", "")

    return StreamingResponse(stream(), media_type="text/event-stream")

"""POST /api/v1/chat — SSE streaming RAG answer.

Skeleton: emits empty `sources` then `done`. Task 3.3 wires retrieval,
live metrics, and Claude streaming in that order so the client can render
citations before tokens arrive.
"""
from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    region_hint: str | None = Field(default=None, description="horqin | hunshandake")


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    async def stream() -> AsyncGenerator[str, None]:
        yield _sse("sources", json.dumps([]))
        yield _sse("done", "")

    return StreamingResponse(stream(), media_type="text/event-stream")

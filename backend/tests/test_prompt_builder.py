"""Unit tests for prompt template builders (pure, no I/O)."""
from __future__ import annotations

from rag.prompt_templates import (
    build_prompt,
    render_metrics_block,
    render_sources_block,
)
from rag.types import Chunk, SearchResult


def _mk_result(source: str, page: int, text: str) -> SearchResult:
    return SearchResult(
        chunk=Chunk(
            text=text,
            source=source,
            title=source.replace("_", " "),
            category="papers_en",
            page=page,
            lang="en",
            region_hint=[],
            chunk_id="",
        ),
        score=0.9,
    )


def test_render_sources_block_numbered_from_1() -> None:
    results = [_mk_result("a.pdf", 1, "alpha"), _mk_result("b.pdf", 2, "beta")]
    block = render_sources_block(results)
    assert "[1]" in block and "[2]" in block
    assert "a.pdf" in block and "b.pdf" in block


def test_render_metrics_block_none_returns_empty() -> None:
    assert render_metrics_block(None).strip() == "(实时数据不可用)"


def test_render_metrics_block_filled() -> None:
    snap = {
        "region": "horqin",
        "timestamp": "2026-04-01T00:00:00Z",
        "ndvi": 0.38,
        "fvc": 42,
        "risk_level": 2,
        "wind_speed": 3.2,
        "soil_moisture": 18,
        "last_alert": None,
    }
    block = render_metrics_block(snap)
    assert "horqin" in block
    assert "0.38" in block
    assert "2" in block  # risk level


def test_build_prompt_includes_all_sections() -> None:
    results = [_mk_result("a.pdf", 1, "sample chunk text")]
    snap = {
        "region": "horqin",
        "timestamp": "t",
        "ndvi": 0.3,
        "fvc": 30,
        "risk_level": 2,
        "wind_speed": 3,
        "soil_moisture": 20,
        "last_alert": None,
    }
    prompt = build_prompt("问题", results, snap)
    assert "问题" in prompt
    assert "[1]" in prompt
    assert "horqin" in prompt


def test_build_prompt_without_metrics() -> None:
    results = [_mk_result("a.pdf", 1, "sample")]
    prompt = build_prompt("问题", results, None)
    assert "问题" in prompt
    assert "(实时数据不可用)" in prompt

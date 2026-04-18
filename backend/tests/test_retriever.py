"""Integration tests for the dense retriever.

Depends on a populated Chroma collection (run `python -m rag.ingest --rebuild
--docs rag/docs` before running these) and the bge-m3 model being downloaded.
Marked `slow` for the same reason test_embedder.py is.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow


def test_retrieve_horqin_returns_relevant() -> None:
    from rag.retriever import retrieve

    results = retrieve("科尔沁沙地近年 NDVI 变化", region=None, top_k=5)
    assert len(results) >= 3
    sources = [r.chunk.source for r in results]
    assert any(
        "inner_mongolia" in s.lower()
        or "horqin" in s.lower()
        or "three-north" in s.lower()
        for s in sources
    )


def test_retrieve_with_region_filter() -> None:
    from rag.retriever import retrieve

    results = retrieve("沙漠化风险", region="hunshandake", top_k=5)
    assert len(results) >= 1
    for r in results:
        assert "hunshandake" in r.chunk.region_hint or r.chunk.region_hint == []


def test_retrieve_scores_descending() -> None:
    from rag.retriever import retrieve

    results = retrieve("afforestation soil carbon", region=None, top_k=10)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_retrieve_rerank_improves_ordering() -> None:
    """A highly specific query should place the matching paper first after rerank."""
    from rag.retriever import retrieve

    results = retrieve(
        "Caragana korshinskii drought response Loess Plateau",
        region=None,
        top_k=3,
        use_rerank=True,
    )
    assert len(results) >= 1
    assert "caragana" in results[0].chunk.source.lower()


def test_retrieve_no_rerank_returns_top_k() -> None:
    """Dense-only fallback path still returns top_k results."""
    from rag.retriever import retrieve

    results = retrieve("wind erosion", region=None, top_k=5, use_rerank=False)
    assert len(results) == 5

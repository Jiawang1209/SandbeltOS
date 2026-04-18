"""Tests for rag.reranker.

Gated behind pytest.mark.slow — first run downloads bge-reranker-v2-m3 (~600MB).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow


def test_reranker_scores_relevant_higher() -> None:
    from rag.reranker import get_reranker

    rr = get_reranker()
    pairs = [
        ("科尔沁沙地 NDVI 趋势", "科尔沁沙地的 NDVI 在 2015-2020 年间上升 12%，植被恢复显著。"),
        ("科尔沁沙地 NDVI 趋势", "Populus euphratica in Tarim river basin shows drought adaptation."),
    ]
    scores = rr.score(pairs)
    assert len(scores) == 2
    assert scores[0] > scores[1]


def test_reranker_singleton() -> None:
    from rag.reranker import get_reranker

    assert get_reranker() is get_reranker()


def test_reranker_empty_pairs() -> None:
    from rag.reranker import get_reranker

    assert get_reranker().score([]) == []

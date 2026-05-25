"""Unit tests for VectorStore region filtering.

Uses fake embeddings + a temp persist dir so these run fast (no model
download, no network), unlike the model-dependent `slow` retriever tests.
"""
from __future__ import annotations

import numpy as np
import pytest

from rag.types import Chunk
from rag.vector_store import VectorStore

pytestmark = pytest.mark.unit


def _chunk(source: str, region_hint: list[str]) -> Chunk:
    return Chunk(
        text=f"text of {source}",
        source=source,
        title=source,
        category="papers_en",
        page=1,
        lang="en",
        region_hint=region_hint,
        chunk_id=f"{source}#p1#c0",
    )


def test_region_filter_keeps_unhinted_chunks(tmp_path) -> None:
    """A region-filtered query must still surface chunks that carry no
    region_hint (general literature), while excluding chunks hinted to a
    *different* region."""
    store = VectorStore(persist_dir=str(tmp_path / "chroma"))
    chunks = [
        _chunk("horqin_paper.pdf", ["horqin"]),
        _chunk("general_paper.pdf", []),  # no region tag -> globally eligible
        _chunk("hunshandake_paper.pdf", ["hunshandake"]),
    ]
    embeddings = np.array(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    store.upsert(chunks, embeddings)

    q = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    results = store.query(q, n_results=10, region_filter="horqin")
    sources = {r.chunk.source for r in results}

    assert "horqin_paper.pdf" in sources  # matching region
    assert "general_paper.pdf" in sources  # no hint -> must NOT be filtered out
    assert "hunshandake_paper.pdf" not in sources  # other region -> excluded

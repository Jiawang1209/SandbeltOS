"""Tests for backend.rag.embedder.

Gated behind pytest.mark.slow because bge-m3 first-run downloads ~2.3GB
and loads a transformer model into memory. Run with `-m slow` or
`-m 'slow or not slow'` to include.
"""
from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.slow


def test_embedder_encode_batch_returns_1024d() -> None:
    from rag.embedder import Embedder

    emb = Embedder()
    vecs = emb.encode(["三北防护林", "Three-North Shelter Forest"])
    assert vecs.shape == (2, 1024)
    assert vecs.dtype == np.float32


def test_embedder_singleton_identity() -> None:
    from rag.embedder import get_embedder

    assert get_embedder() is get_embedder()


def test_embedder_encode_single_string() -> None:
    from rag.embedder import get_embedder

    vec = get_embedder().encode("科尔沁沙地")
    assert vec.shape == (1024,)
    assert vec.dtype == np.float32

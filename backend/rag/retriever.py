"""Dense retriever (pre-rerank stage).

Thin orchestrator: embed query with bge-m3 -> query Chroma -> return
top-K SearchResult. Reranking lives in rag/reranker.py (Task 2.5 will
layer it on top of this).
"""
from __future__ import annotations

import sys

from app.config import settings
from rag.embedder import get_embedder
from rag.types import SearchResult
from rag.vector_store import VectorStore

_store: VectorStore | None = None


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def retrieve(
    query: str,
    region: str | None = None,
    top_k: int | None = None,
) -> list[SearchResult]:
    """Dense retrieve top-K chunks. Rerank is added in Task 2.5."""
    k = top_k or settings.rag_top_k_rerank
    embedder = get_embedder()
    store = _get_store()
    q_emb = embedder.encode(query)
    results = store.query(q_emb, n_results=k, region_filter=region)
    # Chroma already returns sorted by distance; explicit sort for safety.
    return sorted(results, key=lambda r: r.score, reverse=True)


def cli() -> None:
    """Manual smoke test: python -m rag.retriever '<query>' [region]"""
    if len(sys.argv) < 2:
        print("Usage: python -m rag.retriever '<query>' [region]", file=sys.stderr)
        sys.exit(1)
    query = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else None
    for i, r in enumerate(retrieve(query, region, top_k=5), start=1):
        print(f"[{i}] {r.score:.3f} {r.chunk.source} p.{r.chunk.page}")
        print(f"    {r.chunk.text[:120]}...")


if __name__ == "__main__":
    cli()

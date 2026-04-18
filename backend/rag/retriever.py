"""Two-stage retriever: dense top-N → bge-reranker → top-K.

Dense-only path (use_rerank=False) is kept as a fallback for latency-
sensitive or reranker-unavailable scenarios.
"""
from __future__ import annotations

import sys

from app.config import settings
from rag.embedder import get_embedder
from rag.reranker import get_reranker
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
    use_rerank: bool = True,
) -> list[SearchResult]:
    """Retrieve top-K chunks.

    With `use_rerank=True` (default): dense top-N → bge-reranker → top-K.
    With `use_rerank=False`: dense top-K directly (cosine similarity only).
    """
    rerank_k = top_k or settings.rag_top_k_rerank
    embedder = get_embedder()
    store = _get_store()
    q_emb = embedder.encode(query)

    if not use_rerank:
        results = store.query(q_emb, n_results=rerank_k, region_filter=region)
        return sorted(results, key=lambda r: r.score, reverse=True)

    candidates = store.query(
        q_emb, n_results=settings.rag_top_k_retrieve, region_filter=region
    )
    if not candidates:
        return []

    rr = get_reranker()
    pairs = [(query, c.chunk.text) for c in candidates]
    scores = rr.score(pairs)
    reranked = [
        SearchResult(chunk=c.chunk, score=float(s))
        for c, s in zip(candidates, scores)
    ]
    reranked.sort(key=lambda r: r.score, reverse=True)
    return reranked[:rerank_k]


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

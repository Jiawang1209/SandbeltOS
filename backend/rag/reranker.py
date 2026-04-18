"""bge-reranker-v2-m3 wrapper. Lazy-loaded singleton.

The reranker operates on (query, passage) pairs and returns a relevance
score where higher = more relevant. Used in Task 2.5 to refine dense
top-20 candidates down to top-5 for prompt assembly.
"""
from __future__ import annotations

from functools import lru_cache

from app.config import settings


class Reranker:
    def __init__(self, model_name: str | None = None) -> None:
        from FlagEmbedding import FlagReranker  # lazy import — heavy torch load

        self.model_name = model_name or settings.rag_reranker
        self._model = FlagReranker(self.model_name, use_fp16=True)

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Score (query, passage) pairs; higher = more relevant."""
        if not pairs:
            return []
        raw = self._model.compute_score([list(p) for p in pairs], normalize=True)
        if isinstance(raw, float):
            return [raw]
        return [float(x) for x in raw]


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    return Reranker()

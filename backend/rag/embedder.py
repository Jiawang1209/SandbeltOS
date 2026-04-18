"""bge-m3 embedder wrapper. Lazy-loaded singleton."""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.config import settings


class Embedder:
    """Thin wrapper around FlagEmbedding.BGEM3FlagModel for dense retrieval.

    bge-m3 supports dense + sparse + colbert vectors; we only use the
    1024-d dense output for Chroma storage and reranking candidates.
    """

    def __init__(self, model_name: str | None = None) -> None:
        # Import lazily so importing this module doesn't force a torch load
        # in unrelated tests / CLI paths.
        from FlagEmbedding import BGEM3FlagModel

        self.model_name = model_name or settings.rag_embedder
        self._model = BGEM3FlagModel(self.model_name, use_fp16=True)

    def encode(self, texts: str | list[str]) -> np.ndarray:
        """Return dense embeddings.

        single str → shape (1024,); list[str] → (N, 1024), always float32.
        """
        single = isinstance(texts, str)
        batch = [texts] if single else texts
        out = self._model.encode(
            batch,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        dense = np.asarray(out["dense_vecs"], dtype=np.float32)
        return dense[0] if single else dense


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder()

"""Chroma persistent vector store adapter.

Single collection `sandbelt_corpus` with cosine distance. Metadata
stores source / title / category / page / lang / region_hint (joined
as CSV because Chroma metadata must be scalar).

Region filtering is done post-query in Python: Chroma's `where` clause
doesn't support substring match against list-like metadata, so we
over-fetch (n_results × 3) and filter client-side.
"""
from __future__ import annotations

from pathlib import Path

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from rag.types import Chunk, SearchResult

COLLECTION_NAME = "sandbelt_corpus"


class VectorStore:
    def __init__(self, persist_dir: str | None = None) -> None:
        path = persist_dir or settings.chroma_persist_dir
        Path(path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        if not chunks:
            return
        assert embeddings.shape[0] == len(chunks), (
            f"embeddings shape {embeddings.shape} does not match {len(chunks)} chunks"
        )
        self._col.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=embeddings.tolist(),
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "source": c.source,
                    "title": c.title,
                    "category": c.category,
                    "page": c.page,
                    "lang": c.lang,
                    "region_hint": ",".join(c.region_hint),
                }
                for c in chunks
            ],
        )

    def query(
        self,
        query_embedding: np.ndarray,
        n_results: int = 20,
        region_filter: str | None = None,
    ) -> list[SearchResult]:
        # Over-fetch when we need to post-filter by region, since Chroma's
        # `where` clause can't do substring matching against the CSV hint.
        fetch = n_results * 3 if region_filter else n_results
        res = self._col.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=fetch,
        )

        results: list[SearchResult] = []
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists = res["distances"][0]
        for doc, meta, dist in zip(docs, metas, dists):
            raw_hints = (meta.get("region_hint") or "") if meta else ""
            hints = [h for h in raw_hints.split(",") if h]
            if region_filter and region_filter not in hints:
                continue
            chunk = Chunk(
                text=doc,
                source=meta["source"],
                title=meta["title"],
                category=meta["category"],
                page=int(meta["page"]),
                lang=meta["lang"],
                region_hint=hints,
                chunk_id="",  # not returned from query
            )
            # cosine distance -> similarity in [0, 1]
            score = 1.0 - float(dist)
            results.append(SearchResult(chunk=chunk, score=score))
            if len(results) >= n_results:
                break
        return results

    def count(self) -> int:
        return self._col.count()

    def clear(self) -> None:
        """Drop and recreate the collection."""
        self._client.delete_collection(COLLECTION_NAME)
        self._col = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

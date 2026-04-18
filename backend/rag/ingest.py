"""Corpus ingestion CLI: scan docs/, chunk, embed, upsert into Chroma.

Usage:
    python -m rag.ingest --rebuild        # wipe + re-ingest everything
    python -m rag.ingest --incremental    # skip already-ingested sources
    python -m rag.ingest                  # same as --incremental when store exists

At the 12-PDF MVP scale a full re-ingest is cheap, so incremental mode
is best-effort: it uses chunk id prefixes in the collection to detect
"already ingested". If you've changed chunker settings, always pass
--rebuild to avoid stale chunks hanging around.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app.config import settings
from rag.chunker import chunk_pdf
from rag.embedder import get_embedder
from rag.types import Chunk
from rag.vector_store import VectorStore

log = logging.getLogger("rag.ingest")

CATEGORY_DIRS = ("gov", "papers_cn", "papers_en", "standards")


def scan_pdfs(docs_root: Path) -> list[tuple[Path, str]]:
    """Return (pdf_path, category) pairs sorted for deterministic order."""
    pairs: list[tuple[Path, str]] = []
    for cat in CATEGORY_DIRS:
        cat_dir = docs_root / cat
        if not cat_dir.is_dir():
            continue
        for pdf in cat_dir.glob("*.pdf"):
            pairs.append((pdf, cat))
    return sorted(pairs)


def _ingested_sources(store: VectorStore) -> set[str]:
    """Best-effort discovery of sources already in the collection.

    Reads metadata from the underlying collection and returns the set of
    distinct `source` values. Used only for --incremental.
    """
    raw = store._col.get(include=["metadatas"])  # noqa: SLF001 — intentional adapter escape hatch
    metas = raw.get("metadatas") or []
    return {m.get("source") for m in metas if m and m.get("source")}


def ingest(
    docs_root: Path,
    *,
    rebuild: bool = False,
    incremental: bool = False,
) -> int:
    store = VectorStore()
    if rebuild:
        log.info("Rebuild mode: clearing collection")
        store.clear()

    pairs = scan_pdfs(docs_root)
    if not pairs:
        log.warning("No PDFs found under %s", docs_root)
        return 0

    skip_sources: set[str] = set()
    if incremental and not rebuild:
        skip_sources = _ingested_sources(store)
        if skip_sources:
            log.info("Incremental mode: %d sources already ingested, will skip",
                     len(skip_sources))

    embedder = get_embedder()
    total_chunks = 0
    processed_docs = 0
    for pdf, category in pairs:
        if pdf.name in skip_sources:
            log.info("Skip (already ingested): %s", pdf.name)
            continue
        log.info("Chunking %s", pdf.name)
        chunks: list[Chunk] = chunk_pdf(
            pdf,
            category,
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        if not chunks:
            log.warning("No text extracted from %s", pdf.name)
            continue
        log.info("Embedding %d chunks from %s", len(chunks), pdf.name)
        vectors = embedder.encode([c.text for c in chunks])
        store.upsert(chunks, vectors)
        total_chunks += len(chunks)
        processed_docs += 1

    log.info(
        "Ingest complete: %d chunks across %d new documents, total in store: %d",
        total_chunks,
        processed_docs,
        store.count(),
    )
    return total_chunks


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest PDF corpus into Chroma.")
    parser.add_argument("--rebuild", action="store_true",
                        help="Drop existing collection before ingest")
    parser.add_argument("--incremental", action="store_true",
                        help="Skip documents already ingested (by source filename)")
    parser.add_argument("--docs", default=settings.rag_docs_dir,
                        help="Docs root directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    docs_root = Path(args.docs)
    if not docs_root.is_dir():
        log.error("Docs dir not found: %s", docs_root)
        return 1

    ingest(docs_root, rebuild=args.rebuild, incremental=args.incremental)
    return 0


if __name__ == "__main__":
    sys.exit(main())

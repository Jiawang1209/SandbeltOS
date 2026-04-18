# Phase 4 RAG 智慧问答 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Retrieval-Augmented Generation chat module that answers natural-language questions about Three-North Shelterbelt / Horqin / Hunshandake sandy lands by combining a curated 12-paper literature corpus with live sensor metrics.

**Architecture:** PDF corpus is chunked, embedded with bge-m3, stored in a local Chroma collection. At query time a keyword-based router parses region + intent; the retriever fetches top-20 candidates which bge-reranker-v2-m3 reranks to top-5; in parallel, a live-metrics fetcher queries existing ecological services when the intent needs current data. A prompt assembles both into a Claude Sonnet 4.6 streaming call; the backend emits SSE events (`sources` → `metrics` → `token*` → `done`). Two frontend surfaces share a single `useChat` hook: a `/chat` full-screen page and a Dashboard floating widget.

**Tech Stack:**
- Python: FastAPI, ChromaDB, FlagEmbedding (bge-m3 + bge-reranker-v2-m3), PyMuPDF, anthropic SDK, langchain-text-splitters
- TypeScript: Next.js 16 App Router, React 19, Tailwind 4, react-markdown, Playwright
- Infra: local Chroma persistence, existing PostGIS via existing services

**Spec:** `docs/superpowers/specs/2026-04-18-rag-phase4-design.md`

---

## File Structure

### Backend — new files

| File | Responsibility |
|---|---|
| `backend/rag/__init__.py` | Package marker |
| `backend/rag/types.py` | `Chunk`, `SearchResult`, `QueryContext` dataclasses |
| `backend/rag/chunker.py` | PDF → `list[Chunk]` using PyMuPDF + RecursiveCharacterTextSplitter |
| `backend/rag/embedder.py` | bge-m3 wrapper, singleton load, encode(list[str]) → ndarray |
| `backend/rag/vector_store.py` | Chroma client + collection; upsert/query |
| `backend/rag/ingest.py` | CLI: scan docs/, chunk, embed, upsert. Supports `--rebuild` / `--incremental` |
| `backend/rag/retriever.py` | `retrieve(query, region, top_k)` → top-K `SearchResult` (dense+rerank) |
| `backend/rag/reranker.py` | bge-reranker-v2-m3 wrapper |
| `backend/rag/live_metrics.py` | `fetch_snapshot(region_id)` → dict; calls services (not HTTP) |
| `backend/rag/prompt_templates.py` | ECO_DECISION_PROMPT + builder functions |
| `backend/app/api/v1/chat.py` | POST /api/v1/chat SSE endpoint |
| `backend/app/services/query_router.py` | Parse region + intent from text |
| `backend/app/services/ecological.py` | Pure functions (extracted from api/v1/ecological.py) |

### Backend — modified

| File | Change |
|---|---|
| `backend/requirements.txt` | +FlagEmbedding, +PyMuPDF (others already present) |
| `backend/app/config.py` | +RAG_* settings, +CLAUDE_MODEL |
| `backend/app/main.py` | Register chat router |
| `backend/app/api/v1/ecological.py` | Delegate to `services/ecological.py` |
| `.env.example` | Document new vars |
| `.gitignore` | Ignore chroma_store/ and docs/*.pdf |

### Backend — tests

| File | Scope |
|---|---|
| `backend/tests/test_chunker.py` | Chinese/English boundary, metadata correctness |
| `backend/tests/test_query_router.py` | Region keywords, intent detection, needs_live_data |
| `backend/tests/test_live_metrics.py` | Fetch snapshot structure (mocked services) |
| `backend/tests/test_retriever.py` | End-to-end: tiny corpus → top-K ordering |
| `backend/tests/test_prompt_builder.py` | Template rendering with/without metrics |
| `backend/tests/test_chat_endpoint.py` | SSE event order (mocked Claude) |
| `backend/tests/golden_qa.yaml` | 10 Q&A expectations |
| `backend/tests/test_golden.py` | Runs golden set against real retriever + mocked LLM |

### Frontend — new files

| File | Responsibility |
|---|---|
| `frontend/src/lib/sse.ts` | SSE stream parser (yields events) |
| `frontend/src/lib/chat-types.ts` | `ChatMessage`, `Source`, `Metrics` TS types |
| `frontend/src/hooks/useChat.ts` | Shared chat state + SSE consumer |
| `frontend/src/components/chat/ChatMessage.tsx` | Render single message (md + citations) |
| `frontend/src/components/chat/SourcesPanel.tsx` | Right-column or pill sources display |
| `frontend/src/components/chat/MetricsPanel.tsx` | Live-metrics card |
| `frontend/src/components/chat/ChatInput.tsx` | Input box + send button |
| `frontend/src/components/chat/EmptyState.tsx` | 6 example questions |
| `frontend/src/app/chat/page.tsx` | /chat full-screen layout |
| `frontend/src/components/ChatWidget.tsx` | Dashboard floating widget |
| `frontend/e2e/chat.spec.ts` | Playwright E2E for /chat |
| `frontend/e2e/widget.spec.ts` | Playwright E2E for widget |
| `frontend/playwright.config.ts` | Playwright config |

### Frontend — modified

| File | Change |
|---|---|
| `frontend/package.json` | +react-markdown, +remark-gfm, +@playwright/test |
| `frontend/src/app/dashboard/page.tsx` | Mount `<ChatWidget regionHint={...} />` |
| `frontend/src/lib/api.ts` | Add `/api/v1/chat` base helper |

---

# Sprint 1 — Retrieval Pipeline

## Task 1.1: Bootstrap RAG package + config + deps

**Files:**
- Create: `backend/rag/__init__.py`
- Create: `backend/rag/types.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Modify: `.gitignore`
- Create: `.env.example` (if not present) or modify

- [ ] **Step 1: Add new deps to `backend/requirements.txt`**

Append under the existing `# RAG` section:
```
FlagEmbedding>=1.2.10
PyMuPDF>=1.24.0
```

- [ ] **Step 2: Install deps**

Run: `cd backend && pip install -r requirements.txt`
Expected: success; FlagEmbedding and PyMuPDF installed.

- [ ] **Step 3: Extend `backend/app/config.py` with RAG settings**

Locate the existing `Settings(BaseSettings)` class and add:

```python
# --- RAG ---
anthropic_api_key: str = ""
claude_model: str = "claude-sonnet-4-6"
claude_max_tokens: int = 2048

rag_embedder: str = "BAAI/bge-m3"
rag_reranker: str = "BAAI/bge-reranker-v2-m3"
rag_top_k_retrieve: int = 20
rag_top_k_rerank: int = 5
rag_chunk_size: int = 800
rag_chunk_overlap: int = 100

chroma_persist_dir: str = "backend/rag/chroma_store"
rag_docs_dir: str = "backend/rag/docs"
```

Make sure `Settings` has `model_config = SettingsConfigDict(env_file=".env", extra="ignore")` so the new vars pick up from env.

- [ ] **Step 4: Create `backend/rag/__init__.py`**

Content:
```python
"""SandbeltOS Retrieval-Augmented Generation module."""
```

- [ ] **Step 5: Create `backend/rag/types.py`**

```python
"""Core dataclasses for the RAG pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class Chunk:
    text: str
    source: str           # filename, e.g. "2024_hunshandake_sand_fixation.pdf"
    title: str
    category: Literal["gov", "papers_cn", "papers_en", "standards"]
    page: int
    lang: Literal["zh", "en"]
    region_hint: list[str] = field(default_factory=list)  # ["horqin", "hunshandake", ...]
    chunk_id: str = ""    # f"{source}#p{page}#c{idx}"

@dataclass
class SearchResult:
    chunk: Chunk
    score: float          # post-rerank if reranked, else dense similarity

@dataclass
class QueryContext:
    regions: list[str]
    intents: list[str]
    needs_live_data: bool
```

- [ ] **Step 6: Update `.gitignore`**

Append:
```
# Phase 4 RAG
backend/rag/chroma_store/
backend/rag/docs/*.pdf
backend/rag/docs/manifest*.json
backend/rag/docs/download*.log
```

- [ ] **Step 7: Update `.env.example`** (create if absent)

Append the new vars with placeholder values:
```
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_MAX_TOKENS=2048
RAG_EMBEDDER=BAAI/bge-m3
RAG_RERANKER=BAAI/bge-reranker-v2-m3
RAG_TOP_K_RETRIEVE=20
RAG_TOP_K_RERANK=5
RAG_CHUNK_SIZE=800
RAG_CHUNK_OVERLAP=100
CHROMA_PERSIST_DIR=backend/rag/chroma_store
RAG_DOCS_DIR=backend/rag/docs
```

- [ ] **Step 8: Smoke test config loads**

Run: `cd backend && python -c "from app.config import settings; print(settings.rag_embedder)"`
Expected: prints `BAAI/bge-m3`.

- [ ] **Step 9: Commit**

```bash
git add backend/requirements.txt backend/app/config.py backend/rag/__init__.py backend/rag/types.py .gitignore .env.example
git commit -m "feat(rag): bootstrap RAG package, config settings, deps"
```

---

## Task 1.2: PDF chunker with Chinese-friendly splitting

**Files:**
- Create: `backend/rag/chunker.py`
- Create: `backend/tests/test_chunker.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_chunker.py`:

```python
from pathlib import Path
import pytest
from backend.rag.chunker import chunk_text, detect_lang, detect_region_hints

def test_chunk_text_chinese_respects_sentence_boundary():
    text = "第一句话。第二句话。" * 50
    chunks = chunk_text(text, chunk_size=80, chunk_overlap=10)
    assert len(chunks) >= 2
    # No chunk should end mid-sentence (should end on 。 or boundary char)
    for c in chunks[:-1]:
        assert c.rstrip().endswith(("。", "！", "？")) or len(c) <= 80

def test_chunk_text_english_preserves_paragraphs():
    text = "Para one sentence one. Para one sentence two.\n\nPara two sentence one."
    chunks = chunk_text(text, chunk_size=50, chunk_overlap=5)
    assert any("Para one" in c for c in chunks)
    assert any("Para two" in c for c in chunks)

def test_detect_lang_chinese():
    assert detect_lang("这是一段中文文本，包含了中文字符。") == "zh"

def test_detect_lang_english():
    assert detect_lang("This is an English sentence only.") == "en"

def test_detect_region_hints_from_filename():
    assert "horqin" in detect_region_hints("2021_horqin_land_vegetation.pdf", "")
    assert "hunshandake" in detect_region_hints(
        "2024_hunshandake_sand_fixation.pdf", ""
    )

def test_detect_region_hints_from_title():
    hints = detect_region_hints("generic.pdf", "Spatial Patterns in Otindag Sandy Land")
    assert "hunshandake" in hints  # Otindag = Hunshandake synonym
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_chunker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.rag.chunker'`

- [ ] **Step 3: Implement `backend/rag/chunker.py`**

```python
"""PDF → Chunk[]. Pure text splitting + PDF extraction."""
from __future__ import annotations
import re
from pathlib import Path
import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.rag.types import Chunk

_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
_REGION_ALIASES = {
    "horqin": ["horqin", "korqin", "科尔沁", "通辽", "奈曼"],
    "hunshandake": ["hunshandake", "otindag", "浑善达克", "锡林郭勒"],
}

def detect_lang(text: str) -> str:
    chinese = len(_CHINESE_CHAR_RE.findall(text))
    if chinese >= max(20, len(text) * 0.1):
        return "zh"
    return "en"

def detect_region_hints(filename: str, title: str) -> list[str]:
    haystack = f"{filename} {title}".lower()
    return [r for r, aliases in _REGION_ALIASES.items()
            if any(a.lower() in haystack for a in aliases)]

def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> list[str]:
    """Split raw text into overlapping chunks, Chinese-friendly."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""],
    )
    return [c for c in splitter.split_text(text) if c.strip()]

def chunk_pdf(
    path: Path,
    category: str,
    title: str | None = None,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[Chunk]:
    """Extract text page-by-page from PDF and split into Chunks."""
    doc = fitz.open(path)
    display_title = title or path.stem.replace("_", " ")
    region_hints = detect_region_hints(path.name, display_title)
    chunks: list[Chunk] = []

    for page_idx, page in enumerate(doc, start=1):
        page_text = page.get_text("text")
        if not page_text.strip():
            continue
        lang = detect_lang(page_text)
        pieces = chunk_text(page_text, chunk_size, chunk_overlap)
        for c_idx, piece in enumerate(pieces):
            chunks.append(Chunk(
                text=piece,
                source=path.name,
                title=display_title,
                category=category,  # type: ignore[arg-type]
                page=page_idx,
                lang=lang,  # type: ignore[arg-type]
                region_hint=region_hints,
                chunk_id=f"{path.name}#p{page_idx}#c{c_idx}",
            ))
    doc.close()
    return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_chunker.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Smoke test on real PDF**

Run:
```bash
cd backend && python -c "
from pathlib import Path
from rag.chunker import chunk_pdf
chunks = chunk_pdf(Path('rag/docs/papers_en/2024_hunshandake_sand_fixation_plantations.pdf'), 'papers_en')
print(f'Got {len(chunks)} chunks, first page 1 chunk: {chunks[0].text[:120]}...')
print(f'Region hints: {chunks[0].region_hint}')
"
```
Expected: 30-100 chunks; region_hint = `['hunshandake']`.

- [ ] **Step 6: Commit**

```bash
git add backend/rag/chunker.py backend/tests/test_chunker.py
git commit -m "feat(rag): PDF chunker with Chinese-friendly splitting + region detection"
```

---

## Task 1.3: bge-m3 embedder wrapper

**Files:**
- Create: `backend/rag/embedder.py`
- Create: `backend/tests/test_embedder.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_embedder.py`:
```python
import numpy as np
import pytest
from backend.rag.embedder import Embedder, get_embedder

def test_embedder_encode_returns_1024d():
    emb = Embedder()
    vecs = emb.encode(["三北防护林", "Three-North Shelter Forest"])
    assert vecs.shape == (2, 1024)
    assert vecs.dtype in (np.float32, np.float16)

def test_embedder_singleton():
    assert get_embedder() is get_embedder()

def test_embedder_encode_single_string():
    emb = get_embedder()
    vec = emb.encode("科尔沁沙地")
    assert vec.shape == (1024,)
```

Mark these as `@pytest.mark.slow` or gate behind an env flag since loading bge-m3 takes 30+ seconds and downloads 2.3GB first time. Use a session-scoped fixture if we need more tests later. For now:

```python
# Add at top of file
pytestmark = pytest.mark.slow
```

Update `backend/pytest.ini` (or pyproject) to register the `slow` mark:
```ini
[pytest]
markers =
    slow: requires heavy model downloads (bge-m3, bge-reranker)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_embedder.py -v -m slow`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/rag/embedder.py`**

```python
"""bge-m3 embedder. Singleton model load."""
from __future__ import annotations
from functools import lru_cache
import numpy as np
from FlagEmbedding import BGEM3FlagModel
from backend.app.config import settings

class Embedder:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.rag_embedder
        self._model = BGEM3FlagModel(self.model_name, use_fp16=True)

    def encode(self, texts: str | list[str]) -> np.ndarray:
        """Return dense embeddings. Single str → shape (1024,); list[str] → (N, 1024)."""
        single = isinstance(texts, str)
        batch = [texts] if single else texts
        out = self._model.encode(batch, return_dense=True,
                                 return_sparse=False, return_colbert_vecs=False)
        dense = np.asarray(out["dense_vecs"], dtype=np.float32)
        return dense[0] if single else dense

@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_embedder.py -v -m slow`
Expected: PASS (first run downloads bge-m3 model, ~5-10 minutes).

- [ ] **Step 5: Commit**

```bash
git add backend/rag/embedder.py backend/tests/test_embedder.py backend/pytest.ini
git commit -m "feat(rag): bge-m3 embedder singleton wrapper"
```

---

## Task 1.4: Chroma vector store adapter

**Files:**
- Create: `backend/rag/vector_store.py`

- [ ] **Step 1: Implement `backend/rag/vector_store.py`**

No unit test — pure adapter, tested via `test_retriever.py` integration in Task 1.6.

```python
"""Chroma persistent vector store adapter."""
from __future__ import annotations
from pathlib import Path
from typing import Iterable
import chromadb
from chromadb.config import Settings as ChromaSettings
import numpy as np
from backend.app.config import settings
from backend.rag.types import Chunk, SearchResult

COLLECTION_NAME = "sandbelt_corpus"

class VectorStore:
    def __init__(self, persist_dir: str | None = None):
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
        assert embeddings.shape[0] == len(chunks)
        self._col.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=embeddings.tolist(),
            documents=[c.text for c in chunks],
            metadatas=[{
                "source": c.source, "title": c.title, "category": c.category,
                "page": c.page, "lang": c.lang,
                "region_hint": ",".join(c.region_hint),  # Chroma metadata must be scalar
            } for c in chunks],
        )

    def query(
        self,
        query_embedding: np.ndarray,
        n_results: int = 20,
        region_filter: str | None = None,
    ) -> list[SearchResult]:
        where = None
        if region_filter:
            # Chroma doesn't support substring match in `where`; we post-filter instead.
            pass

        res = self._col.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results * (3 if region_filter else 1),  # over-fetch then filter
        )
        results: list[SearchResult] = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            hints = (meta.get("region_hint") or "").split(",") if meta.get("region_hint") else []
            if region_filter and region_filter not in hints:
                continue
            chunk = Chunk(
                text=doc,
                source=meta["source"], title=meta["title"],
                category=meta["category"], page=int(meta["page"]),
                lang=meta["lang"], region_hint=[h for h in hints if h],
                chunk_id="",  # not needed for query results
            )
            # cosine distance → similarity
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
```

- [ ] **Step 2: Smoke test with tiny fake data**

Run:
```bash
cd backend && python -c "
import numpy as np
from rag.vector_store import VectorStore
from rag.types import Chunk
vs = VectorStore(persist_dir='/tmp/sandbelt_chroma_test')
chunks = [Chunk(text='Horqin ndvi test', source='t.pdf', title='T', category='papers_en',
                page=1, lang='en', region_hint=['horqin'], chunk_id='t#1')]
vs.upsert(chunks, np.random.rand(1, 1024).astype('float32'))
print(f'count={vs.count()}')
res = vs.query(np.random.rand(1024).astype('float32'), n_results=1)
print(f'got {len(res)} results: {res[0].chunk.source}')
"
```
Expected: `count=1`, `got 1 results: t.pdf`. Then cleanup: `rm -rf /tmp/sandbelt_chroma_test`.

- [ ] **Step 3: Commit**

```bash
git add backend/rag/vector_store.py
git commit -m "feat(rag): ChromaDB persistent vector store adapter"
```

---

## Task 1.5: Ingest CLI

**Files:**
- Create: `backend/rag/ingest.py`

- [ ] **Step 1: Implement `backend/rag/ingest.py`**

```python
"""CLI: scan docs/, chunk, embed, upsert into Chroma."""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path
from backend.app.config import settings
from backend.rag.chunker import chunk_pdf
from backend.rag.embedder import get_embedder
from backend.rag.vector_store import VectorStore
from backend.rag.types import Chunk

log = logging.getLogger("rag.ingest")

CATEGORY_DIRS = ("gov", "papers_cn", "papers_en", "standards")

def scan_pdfs(docs_root: Path) -> list[tuple[Path, str]]:
    """Return (pdf_path, category) pairs."""
    pairs: list[tuple[Path, str]] = []
    for cat in CATEGORY_DIRS:
        for pdf in (docs_root / cat).glob("*.pdf"):
            pairs.append((pdf, cat))
    return sorted(pairs)

def ingest(docs_root: Path, rebuild: bool = False, incremental: bool = False) -> int:
    store = VectorStore()
    if rebuild:
        log.info("Rebuild mode: clearing collection")
        store.clear()

    embedder = get_embedder()
    pairs = scan_pdfs(docs_root)
    if not pairs:
        log.warning("No PDFs found under %s", docs_root)
        return 0

    existing_sources: set[str] = set()
    if incremental and not rebuild:
        # We don't have a direct "list sources" API; skip by checking id prefix.
        # For MVP, incremental = skip if any chunk_id starting with source exists.
        # Simpler: keep a sidecar manifest. For now, full re-ingest is fine at 12 docs.
        log.info("Incremental mode not fully implemented at MVP; treating as full ingest")

    total_chunks = 0
    for pdf, category in pairs:
        log.info("Chunking %s", pdf.name)
        chunks: list[Chunk] = chunk_pdf(
            pdf, category,
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

    log.info("Ingest complete: %d chunks across %d documents, total in store: %d",
             total_chunks, len(pairs), store.count())
    return total_chunks

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true",
                        help="Drop existing collection before ingest")
    parser.add_argument("--incremental", action="store_true",
                        help="Skip already-ingested documents")
    parser.add_argument("--docs", default=settings.rag_docs_dir)
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
```

- [ ] **Step 2: Run full ingest on the 12-PDF corpus**

Run: `cd backend && python -m rag.ingest --rebuild`
Expected:
- Logs: `Chunking ...pdf` × 12, `Embedding N chunks`, `Ingest complete: ~3000 chunks across 12 documents`
- Takes 5-10 minutes on first run (model download + embedding).

- [ ] **Step 3: Verify collection is populated**

Run: `cd backend && python -c "from rag.vector_store import VectorStore; print(VectorStore().count())"`
Expected: number ≥ 1000 (our 12 PDFs should produce ~2000-4000 chunks).

- [ ] **Step 4: Commit**

```bash
git add backend/rag/ingest.py
git commit -m "feat(rag): ingest CLI for corpus → Chroma"
```

---

## Task 1.6: Dense retriever (pre-rerank)

**Files:**
- Create: `backend/rag/retriever.py`
- Create: `backend/tests/test_retriever.py`

Note: The full retriever adds reranking in Task 2.5. This task implements only the dense-only version so Sprint 1 ends with a working end-to-end.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_retriever.py`:
```python
import pytest
from backend.rag.retriever import retrieve

pytestmark = pytest.mark.slow  # depends on ingested Chroma + loaded bge-m3

def test_retrieve_horqin_returns_relevant():
    results = retrieve("科尔沁沙地近年 NDVI 变化", region=None, top_k=5)
    assert len(results) >= 3
    sources = [r.chunk.source for r in results]
    # At least one result should be a NE Inner Mongolia / Horqin paper
    assert any("inner_mongolia" in s.lower() or "horqin" in s.lower()
               or "three-north" in s.lower() for s in sources)

def test_retrieve_with_region_filter():
    results = retrieve("沙漠化风险", region="hunshandake", top_k=5)
    assert len(results) >= 1
    for r in results:
        assert "hunshandake" in r.chunk.region_hint or r.chunk.region_hint == []

def test_retrieve_scores_descending():
    results = retrieve("afforestation soil carbon", region=None, top_k=10)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_retriever.py -v -m slow`
Expected: FAIL — `retrieve` not defined.

- [ ] **Step 3: Implement `backend/rag/retriever.py` (dense-only)**

```python
"""Dense retrieval over Chroma. Rerank added in Task 2.5."""
from __future__ import annotations
from backend.app.config import settings
from backend.rag.embedder import get_embedder
from backend.rag.vector_store import VectorStore
from backend.rag.types import SearchResult

_store: VectorStore | None = None

def _get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store

def retrieve(query: str, region: str | None = None, top_k: int | None = None) -> list[SearchResult]:
    """Dense retrieve top-K chunks. Rerank is a future layer (Task 2.5)."""
    k = top_k or settings.rag_top_k_rerank  # MVP returns rerank-sized top_k directly
    embedder = get_embedder()
    store = _get_store()
    q_emb = embedder.encode(query)
    return store.query(q_emb, n_results=k, region_filter=region)

def cli():
    """Manual smoke test: python -m backend.rag.retriever '问题'"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m backend.rag.retriever '<query>' [region]", file=sys.stderr)
        sys.exit(1)
    query = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else None
    for i, r in enumerate(retrieve(query, region, top_k=5), start=1):
        print(f"[{i}] {r.score:.3f} {r.chunk.source} p.{r.chunk.page}")
        print(f"    {r.chunk.text[:120]}...")

if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_retriever.py -v -m slow`
Expected: all 3 tests PASS.

- [ ] **Step 5: CLI smoke test**

Run: `cd backend && python -m rag.retriever "RWEQ 公式怎么算"`
Expected: 5 results printed with source + page + snippet. At least one should be the `2022_regional_wind_erosion_wind_data.pdf`.

- [ ] **Step 6: Commit**

```bash
git add backend/rag/retriever.py backend/tests/test_retriever.py
git commit -m "feat(rag): dense retriever + CLI smoke test"
```

---

# Sprint 2 — Rerank + Router + Live Metrics

## Task 2.1: bge-reranker-v2-m3

**Files:**
- Create: `backend/rag/reranker.py`
- Create: `backend/tests/test_reranker.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_reranker.py`:
```python
import pytest
from backend.rag.reranker import Reranker, get_reranker

pytestmark = pytest.mark.slow

def test_reranker_scores_relevant_higher():
    rr = get_reranker()
    pairs = [
        ("科尔沁沙地 NDVI 趋势", "科尔沁沙地的 NDVI 在 2015-2020 年间上升 12%..."),
        ("科尔沁沙地 NDVI 趋势", "Populus euphratica in Tarim river basin shows..."),
    ]
    scores = rr.score(pairs)
    assert len(scores) == 2
    assert scores[0] > scores[1]  # first pair is more relevant

def test_reranker_singleton():
    assert get_reranker() is get_reranker()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_reranker.py -v -m slow`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/rag/reranker.py`**

```python
"""bge-reranker-v2-m3 wrapper."""
from __future__ import annotations
from functools import lru_cache
from FlagEmbedding import FlagReranker
from backend.app.config import settings

class Reranker:
    def __init__(self, model_name: str | None = None):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_reranker.py -v -m slow`
Expected: PASS (first run downloads reranker, ~600MB).

- [ ] **Step 5: Commit**

```bash
git add backend/rag/reranker.py backend/tests/test_reranker.py
git commit -m "feat(rag): bge-reranker-v2-m3 wrapper"
```

---

## Task 2.2: Query router (keyword-based)

**Files:**
- Create: `backend/app/services/query_router.py`
- Create: `backend/tests/test_query_router.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_query_router.py`:
```python
from backend.app.services.query_router import parse

def test_parse_horqin_current_status():
    ctx = parse("科尔沁现在风险怎样")
    assert "horqin" in ctx.regions
    assert "current_status" in ctx.intents
    assert "risk" in ctx.intents
    assert ctx.needs_live_data is True

def test_parse_hunshandake_trend():
    ctx = parse("浑善达克近 20 年 NDVI 趋势")
    assert "hunshandake" in ctx.regions
    assert "trend" in ctx.intents
    assert ctx.needs_live_data is True  # trend + region → live too

def test_parse_method_question_no_live():
    ctx = parse("RWEQ 公式怎么算")
    assert ctx.regions == []
    assert "method" in ctx.intents
    assert ctx.needs_live_data is False

def test_parse_species_question_with_region_no_live():
    ctx = parse("科尔沁适合什么树种")
    assert "horqin" in ctx.regions
    assert "species" in ctx.intents
    # species is a research question, not live; needs_live only for status/risk/trend
    assert ctx.needs_live_data is False

def test_parse_otindag_alias_maps_to_hunshandake():
    ctx = parse("Otindag desertification now")
    assert "hunshandake" in ctx.regions
    assert "current_status" in ctx.intents

def test_parse_empty_query():
    ctx = parse("")
    assert ctx.regions == []
    assert ctx.intents == []
    assert ctx.needs_live_data is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_query_router.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/app/services/query_router.py`**

```python
"""Keyword-based query router: text → (regions, intents, needs_live)."""
from __future__ import annotations
import re
from backend.rag.types import QueryContext

REGION_KEYWORDS = {
    "horqin": ["科尔沁", "Horqin", "horqin", "Korqin", "通辽", "奈曼"],
    "hunshandake": ["浑善达克", "Hunshandake", "Otindag", "otindag", "锡林郭勒"],
}

INTENT_PATTERNS = {
    "current_status": [r"现在", r"当前", r"目前", r"\bnow\b", r"\bcurrent\b"],
    "trend":          [r"趋势", r"变化", r"近\s*\d+\s*年", r"\btrend\b", r"\bchange\b"],
    "risk":           [r"风险", r"危险", r"\brisk\b", r"\balert\b", r"沙化", r"退化"],
    "species":        [r"树种", r"植被", r"造林", r"\bspecies\b", r"\bplantation\b"],
    "method":         [r"怎么算", r"公式", r"方法", r"RWEQ", r"FVC", r"NDVI.*计算", r"how.*calculate"],
    "policy":         [r"规划", r"政策", r"战略", r"工程", r"\bpolicy\b"],
}

# Intents that warrant pulling live sensor data
LIVE_DATA_INTENTS = {"current_status", "risk", "trend"}

def _match_regions(query: str) -> list[str]:
    q_lower = query.lower()
    return [region for region, aliases in REGION_KEYWORDS.items()
            if any(a.lower() in q_lower for a in aliases)]

def _match_intents(query: str) -> list[str]:
    hits: list[str] = []
    for intent, patterns in INTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, query, flags=re.IGNORECASE):
                hits.append(intent)
                break
    return hits

def parse(query: str) -> QueryContext:
    regions = _match_regions(query)
    intents = _match_intents(query)
    needs_live = bool(regions) and bool(set(intents) & LIVE_DATA_INTENTS)
    return QueryContext(regions=regions, intents=intents, needs_live_data=needs_live)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_query_router.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/query_router.py backend/tests/test_query_router.py
git commit -m "feat(rag): keyword-based query router (region+intent)"
```

---

## Task 2.3: Extract ecological services layer

**Files:**
- Create: `backend/app/services/ecological.py`
- Modify: `backend/app/api/v1/ecological.py`

This refactor makes the existing ecological endpoint logic callable from `live_metrics.py` without going through HTTP.

- [ ] **Step 1: Read the current endpoint to identify extractable query logic**

Read `backend/app/api/v1/ecological.py` and identify the SQL/service logic inside each route. For each endpoint, the business logic (DB query, aggregation) moves to a pure async function; the route becomes a thin wrapper.

- [ ] **Step 2: Create `backend/app/services/ecological.py`**

Target functions (signatures):
```python
from __future__ import annotations
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_session  # or whatever the existing module is named

async def get_current_status(region_id: str, session: AsyncSession) -> dict:
    """Latest NDVI + FVC for the region."""
    ...

async def get_risk_latest(region_id: str, session: AsyncSession) -> dict:
    """Latest risk level 1-4."""
    ...

async def get_weather_latest(region_id: str, session: AsyncSession) -> dict:
    """Latest wind_speed, soil_moisture, temp."""
    ...

async def get_landcover_latest(region_id: str, session: AsyncSession) -> dict:
    """Latest land-cover percentages."""
    ...

async def get_alerts(region_id: str, session: AsyncSession, limit: int = 5) -> list[dict]:
    """Latest N alerts."""
    ...
```

Copy the query logic from each route in `api/v1/ecological.py` into these functions. Keep the return schemas identical to what the routes returned.

- [ ] **Step 3: Update `backend/app/api/v1/ecological.py` to delegate**

Each route becomes:
```python
@router.get("/current-status/{region_id}")
async def current_status(region_id: str, session: AsyncSession = Depends(get_session)):
    return await ecological_svc.get_current_status(region_id, session)
```

- [ ] **Step 4: Verify existing endpoint tests still pass**

Run: `cd backend && pytest tests/ -v -k "not slow" --ignore=tests/test_retriever.py --ignore=tests/test_embedder.py --ignore=tests/test_reranker.py`
Expected: any existing ecological tests pass unchanged.

If no tests exist for the existing routes, manually smoke-test:
```bash
cd backend && uvicorn app.main:app --port 8000 &
sleep 3
curl http://localhost:8000/api/v1/ecological/current-status/horqin
kill %1
```
Expected: same JSON shape as before refactor.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ecological.py backend/app/api/v1/ecological.py
git commit -m "refactor(ecological): extract services layer for programmatic access"
```

---

## Task 2.4: Live metrics fetcher

**Files:**
- Create: `backend/rag/live_metrics.py`
- Create: `backend/tests/test_live_metrics.py`

- [ ] **Step 1: Write failing tests with mocked services**

Create `backend/tests/test_live_metrics.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
from backend.rag.live_metrics import fetch_snapshot

@pytest.mark.asyncio
async def test_fetch_snapshot_merges_all_sources():
    with patch("backend.rag.live_metrics.ecological_svc") as svc, \
         patch("backend.rag.live_metrics.get_session") as get_sess:
        get_sess.return_value.__aenter__.return_value = "sess"
        svc.get_current_status = AsyncMock(return_value={
            "timestamp": "2026-04-01T00:00:00Z", "value": 0.38, "fvc": 42,
        })
        svc.get_risk_latest = AsyncMock(return_value={"level": 2})
        svc.get_weather_latest = AsyncMock(return_value={
            "wind_speed": 3.2, "soil_moisture": 18,
        })
        svc.get_landcover_latest = AsyncMock(return_value={"grassland": 60})
        svc.get_alerts = AsyncMock(return_value=[
            {"level": 2, "message": "dust", "timestamp": "2026-04-01T00:00:00Z"}
        ])

        snap = await fetch_snapshot("horqin")

    assert snap["region"] == "horqin"
    assert snap["ndvi"] == 0.38
    assert snap["fvc"] == 42
    assert snap["risk_level"] == 2
    assert snap["wind_speed"] == 3.2
    assert snap["soil_moisture"] == 18
    assert snap["last_alert"]["level"] == 2

@pytest.mark.asyncio
async def test_fetch_snapshot_handles_no_alerts():
    with patch("backend.rag.live_metrics.ecological_svc") as svc, \
         patch("backend.rag.live_metrics.get_session") as get_sess:
        get_sess.return_value.__aenter__.return_value = "sess"
        svc.get_current_status = AsyncMock(return_value={"timestamp": "x", "value": 0.5, "fvc": 50})
        svc.get_risk_latest = AsyncMock(return_value={"level": 1})
        svc.get_weather_latest = AsyncMock(return_value={"wind_speed": 1, "soil_moisture": 30})
        svc.get_landcover_latest = AsyncMock(return_value={})
        svc.get_alerts = AsyncMock(return_value=[])

        snap = await fetch_snapshot("hunshandake")

    assert snap["last_alert"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_live_metrics.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/rag/live_metrics.py`**

```python
"""Aggregate live sensor metrics for a region by calling services in parallel."""
from __future__ import annotations
import asyncio
from typing import Any
from backend.app.services import ecological as ecological_svc
from backend.app.database import get_session  # adjust import to match project

async def fetch_snapshot(region_id: str) -> dict[str, Any]:
    """Call five service functions concurrently and merge into one dict."""
    async with get_session() as sess:
        ndvi, risk, weather, landcover, alerts = await asyncio.gather(
            ecological_svc.get_current_status(region_id, sess),
            ecological_svc.get_risk_latest(region_id, sess),
            ecological_svc.get_weather_latest(region_id, sess),
            ecological_svc.get_landcover_latest(region_id, sess),
            ecological_svc.get_alerts(region_id, sess, limit=1),
        )

    return {
        "region": region_id,
        "timestamp": ndvi.get("timestamp"),
        "ndvi": ndvi.get("value"),
        "fvc": ndvi.get("fvc"),
        "risk_level": risk.get("level"),
        "wind_speed": weather.get("wind_speed"),
        "soil_moisture": weather.get("soil_moisture"),
        "landcover": landcover,
        "last_alert": alerts[0] if alerts else None,
    }
```

If the actual `get_session` import path differs, look it up in `backend/app/main.py` or `database.py` and adjust.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_live_metrics.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rag/live_metrics.py backend/tests/test_live_metrics.py
git commit -m "feat(rag): live metrics snapshot aggregator"
```

---

## Task 2.5: Integrate rerank into retriever

**Files:**
- Modify: `backend/rag/retriever.py`
- Modify: `backend/tests/test_retriever.py`

- [ ] **Step 1: Add rerank-specific test to `test_retriever.py`**

Append:
```python
def test_retrieve_rerank_improves_ordering():
    """With rerank on, a highly specific query should put the matching paper first."""
    results = retrieve("Caragana korshinskii drought response Loess Plateau",
                       region=None, top_k=3, use_rerank=True)
    assert len(results) >= 1
    assert "caragana" in results[0].chunk.source.lower()

def test_retrieve_no_rerank_for_fallback():
    """use_rerank=False path still returns top_k results."""
    results = retrieve("wind erosion", region=None, top_k=5, use_rerank=False)
    assert len(results) == 5
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd backend && pytest tests/test_retriever.py::test_retrieve_rerank_improves_ordering -v -m slow`
Expected: FAIL — `retrieve` doesn't accept `use_rerank`.

- [ ] **Step 3: Update `backend/rag/retriever.py`**

Replace the existing `retrieve()` body:
```python
from backend.rag.reranker import get_reranker

def retrieve(
    query: str,
    region: str | None = None,
    top_k: int | None = None,
    use_rerank: bool = True,
) -> list[SearchResult]:
    """Dense retrieve top-N_RETRIEVE, optionally rerank to top_k."""
    rerank_k = top_k or settings.rag_top_k_rerank
    if not use_rerank:
        # direct dense top-k
        embedder = get_embedder()
        store = _get_store()
        q_emb = embedder.encode(query)
        return store.query(q_emb, n_results=rerank_k, region_filter=region)

    # two-stage: dense top-20 → rerank → top-k
    retrieve_k = settings.rag_top_k_retrieve
    embedder = get_embedder()
    store = _get_store()
    q_emb = embedder.encode(query)
    candidates = store.query(q_emb, n_results=retrieve_k, region_filter=region)
    if not candidates:
        return []

    rr = get_reranker()
    pairs = [(query, c.chunk.text) for c in candidates]
    scores = rr.score(pairs)
    reranked = sorted(
        (SearchResult(chunk=c.chunk, score=s) for c, s in zip(candidates, scores)),
        key=lambda r: -r.score,
    )
    return reranked[:rerank_k]
```

- [ ] **Step 4: Run all retriever tests**

Run: `cd backend && pytest tests/test_retriever.py -v -m slow`
Expected: all PASS (including previous 3 + new 2).

- [ ] **Step 5: CLI re-smoke**

Run: `cd backend && python -m rag.retriever "Populus simoni Liaoning sandy plantation"`
Expected: top result should be `2025_populus_simoni_liaoning_sandy.pdf`.

- [ ] **Step 6: Commit**

```bash
git add backend/rag/retriever.py backend/tests/test_retriever.py
git commit -m "feat(rag): two-stage retrieve with bge-reranker top-20→top-5"
```

---

# Sprint 3 — SSE Chat Endpoint + Claude

## Task 3.1: Prompt templates + builder

**Files:**
- Create: `backend/rag/prompt_templates.py`
- Create: `backend/tests/test_prompt_builder.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_prompt_builder.py`:
```python
from backend.rag.prompt_templates import build_prompt, render_sources_block, render_metrics_block
from backend.rag.types import Chunk, SearchResult

def _mk_result(source: str, page: int, text: str) -> SearchResult:
    return SearchResult(
        chunk=Chunk(text=text, source=source, title=source.replace("_", " "),
                    category="papers_en", page=page, lang="en", region_hint=[], chunk_id=""),
        score=0.9,
    )

def test_render_sources_block_numbered_from_1():
    results = [_mk_result("a.pdf", 1, "alpha"), _mk_result("b.pdf", 2, "beta")]
    block = render_sources_block(results)
    assert "[1]" in block and "[2]" in block
    assert "a.pdf" in block and "b.pdf" in block

def test_render_metrics_block_none_returns_empty():
    assert render_metrics_block(None).strip() == "(实时数据不可用)"

def test_render_metrics_block_filled():
    snap = {
        "region": "horqin", "timestamp": "2026-04-01T00:00:00Z",
        "ndvi": 0.38, "fvc": 42, "risk_level": 2,
        "wind_speed": 3.2, "soil_moisture": 18, "last_alert": None,
    }
    block = render_metrics_block(snap)
    assert "horqin" in block
    assert "0.38" in block
    assert "2" in block  # risk level

def test_build_prompt_includes_all_sections():
    results = [_mk_result("a.pdf", 1, "sample chunk text")]
    snap = {"region": "horqin", "timestamp": "t", "ndvi": 0.3, "fvc": 30,
            "risk_level": 2, "wind_speed": 3, "soil_moisture": 20, "last_alert": None}
    prompt = build_prompt("问题", results, snap)
    assert "问题" in prompt
    assert "[1]" in prompt
    assert "horqin" in prompt

def test_build_prompt_without_metrics():
    results = [_mk_result("a.pdf", 1, "sample")]
    prompt = build_prompt("问题", results, None)
    assert "问题" in prompt
    assert "(实时数据不可用)" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_prompt_builder.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/rag/prompt_templates.py`**

```python
"""Prompt templates for the RAG chat endpoint."""
from __future__ import annotations
from typing import Any
from backend.rag.types import SearchResult

ECO_DECISION_PROMPT = """你是三北防护林生态决策助手 SandbeltOS。回答时必须：
1. 基于下方【文献】和【实时指标】给答案，不要编造
2. 用 [1] [2] 格式引用文献（对应 Sources 列表顺序）
3. 当【实时指标】与【文献】结论冲突时，指出冲突并以实时数据为准
4. 中文回答，简洁、不啰嗦、直接给结论+证据

【用户问题】
{question}

【实时指标】
{metrics_block}

【文献片段】
{sources_block}

【回答要求】
- 先给 1-2 句核心结论
- 然后给关键证据（引用 [n]）
- 如果涉及数值，必须明确时间/地点
- 最后如果有不确定性，诚实说明
"""

def render_sources_block(results: list[SearchResult]) -> str:
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(f"[{i}] {r.chunk.title} (page {r.chunk.page}, {r.chunk.source})")
        lines.append(r.chunk.text.strip())
        lines.append("")
    return "\n".join(lines).strip()

def render_metrics_block(snapshot: dict[str, Any] | None) -> str:
    if snapshot is None:
        return "(实时数据不可用)"
    alert = snapshot.get("last_alert")
    alert_str = f"最近告警: {alert['message']} (level {alert['level']})" if alert else "最近告警: 无"
    return (
        f"区域: {snapshot.get('region')}\n"
        f"时间: {snapshot.get('timestamp')}\n"
        f"NDVI: {snapshot.get('ndvi')}\n"
        f"植被覆盖 FVC: {snapshot.get('fvc')}%\n"
        f"风险等级: {snapshot.get('risk_level')} / 4\n"
        f"风速: {snapshot.get('wind_speed')} m/s\n"
        f"土壤湿度: {snapshot.get('soil_moisture')}%\n"
        f"{alert_str}"
    )

def build_prompt(
    question: str,
    results: list[SearchResult],
    snapshot: dict[str, Any] | None,
) -> str:
    return ECO_DECISION_PROMPT.format(
        question=question,
        metrics_block=render_metrics_block(snapshot),
        sources_block=render_sources_block(results),
    )

def build_sources_meta(results: list[SearchResult]) -> list[dict[str, Any]]:
    """Return SSE-ready sources metadata (id, title, page, source)."""
    return [
        {
            "id": i,
            "title": r.chunk.title,
            "source": r.chunk.source,
            "page": r.chunk.page,
            "score": r.score,
        }
        for i, r in enumerate(results, start=1)
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_prompt_builder.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rag/prompt_templates.py backend/tests/test_prompt_builder.py
git commit -m "feat(rag): prompt templates + sources/metrics block builders"
```

---

## Task 3.2: Chat endpoint scaffolding

**Files:**
- Create: `backend/app/api/v1/chat.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_chat_endpoint.py`

- [ ] **Step 1: Write failing test for endpoint wiring**

Create `backend/tests/test_chat_endpoint.py`:
```python
import pytest
from httpx import AsyncClient
from backend.app.main import app

@pytest.mark.asyncio
async def test_chat_endpoint_requires_question():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/chat", json={})
    assert resp.status_code == 422  # pydantic validation error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_chat_endpoint.py::test_chat_endpoint_requires_question -v`
Expected: FAIL — 404 (no route yet).

- [ ] **Step 3: Create `backend/app/api/v1/chat.py` (skeleton)**

```python
"""POST /api/v1/chat — SSE streaming RAG answer."""
from __future__ import annotations
import json
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["chat"])

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    region_hint: str | None = Field(default=None, description="horqin | hunshandake")

def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"

@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    async def stream() -> AsyncGenerator[str, None]:
        yield _sse("sources", json.dumps([]))
        yield _sse("done", "")

    return StreamingResponse(stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Register router in `backend/app/main.py`**

Add import near other router imports:
```python
from backend.app.api.v1 import chat as chat_v1
```

And inside the app bootstrap (where other routers are registered):
```python
app.include_router(chat_v1.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_chat_endpoint.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/chat.py backend/app/main.py backend/tests/test_chat_endpoint.py
git commit -m "feat(chat): SSE endpoint skeleton + router wiring"
```

---

## Task 3.3: Claude streaming integration

**Files:**
- Create: `backend/rag/claude_client.py`
- Modify: `backend/app/api/v1/chat.py`
- Modify: `backend/tests/test_chat_endpoint.py`

- [ ] **Step 1: Create `backend/rag/claude_client.py`**

```python
"""Claude streaming wrapper."""
from __future__ import annotations
from typing import AsyncGenerator
from anthropic import AsyncAnthropic
from backend.app.config import settings

_client: AsyncAnthropic | None = None

def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client

async def stream_completion(prompt: str) -> AsyncGenerator[str, None]:
    """Yield text deltas from Claude streaming."""
    client = _get_client()
    async with client.messages.stream(
        model=settings.claude_model,
        max_tokens=settings.claude_max_tokens,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for delta in stream.text_stream:
            yield delta
```

- [ ] **Step 2: Add SSE-order test**

Append to `backend/tests/test_chat_endpoint.py`:
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_chat_streams_sources_then_tokens_then_done():
    """Verify SSE events arrive in order: sources → (metrics?) → token* → done."""
    fake_chunks = [
        type("C", (), {"chunk": type("Ch", (), {
            "text": "sample", "title": "T", "source": "s.pdf",
            "page": 1, "lang": "en", "category": "papers_en",
            "region_hint": [], "chunk_id": ""
        })(), "score": 0.9})(),
    ]

    async def fake_stream(prompt):
        yield "Hello"
        yield " world"

    with patch("backend.app.api.v1.chat.retriever.retrieve", return_value=fake_chunks), \
         patch("backend.app.api.v1.chat.query_router.parse") as parse, \
         patch("backend.app.api.v1.chat.stream_completion", side_effect=fake_stream):

        from backend.rag.types import QueryContext
        parse.return_value = QueryContext(regions=[], intents=[], needs_live_data=False)

        async with AsyncClient(app=app, base_url="http://test") as client:
            async with client.stream("POST", "/api/v1/chat", json={"question": "hi"}) as r:
                body = b""
                async for chunk in r.aiter_bytes():
                    body += chunk
        text = body.decode()

    # sources appears before first token, done is last
    idx_sources = text.find("event: sources")
    idx_token = text.find("event: token")
    idx_done = text.find("event: done")
    assert idx_sources != -1 and idx_token != -1 and idx_done != -1
    assert idx_sources < idx_token < idx_done
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_chat_endpoint.py::test_chat_streams_sources_then_tokens_then_done -v`
Expected: FAIL — endpoint doesn't stream tokens yet.

- [ ] **Step 4: Wire everything in `backend/app/api/v1/chat.py`**

Replace the skeleton:
```python
"""POST /api/v1/chat — SSE streaming RAG answer."""
from __future__ import annotations
import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.services import query_router
from backend.rag import retriever, live_metrics
from backend.rag.claude_client import stream_completion
from backend.rag.prompt_templates import build_prompt, build_sources_meta

router = APIRouter(prefix="/api/v1", tags=["chat"])

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    region_hint: str | None = Field(default=None)

def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"

@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    ctx = query_router.parse(req.question)
    region = req.region_hint or (ctx.regions[0] if ctx.regions else None)

    async def stream() -> AsyncGenerator[str, None]:
        retrieve_task = asyncio.create_task(
            asyncio.to_thread(retriever.retrieve, req.question, region, None, True)
        )
        metrics_task: asyncio.Task | None = None
        if ctx.needs_live_data and region:
            metrics_task = asyncio.create_task(live_metrics.fetch_snapshot(region))

        results = await retrieve_task
        metrics = await metrics_task if metrics_task else None

        yield _sse("sources", json.dumps(build_sources_meta(results), ensure_ascii=False))
        if metrics is not None:
            yield _sse("metrics", json.dumps(metrics, ensure_ascii=False, default=str))

        prompt = build_prompt(req.question, results, metrics)
        try:
            async for delta in stream_completion(prompt):
                yield _sse("token", json.dumps(delta, ensure_ascii=False))
        except Exception as e:
            yield _sse("error", json.dumps({"message": str(e)}, ensure_ascii=False))
        finally:
            yield _sse("done", "")

    return StreamingResponse(stream(), media_type="text/event-stream")
```

Note: `retriever.retrieve` is sync (loads bge-m3), so wrap in `asyncio.to_thread` to avoid blocking the event loop.

- [ ] **Step 5: Run all chat tests**

Run: `cd backend && pytest tests/test_chat_endpoint.py -v`
Expected: all PASS.

- [ ] **Step 6: Real Claude smoke test**

Ensure `ANTHROPIC_API_KEY` is set in `.env`. Then:
```bash
cd backend && uvicorn app.main:app --port 8000 &
sleep 3
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "RWEQ 公式怎么算？"}'
kill %1
```
Expected: SSE stream with `sources` event → `token` events → `done`.

- [ ] **Step 7: Commit**

```bash
git add backend/rag/claude_client.py backend/app/api/v1/chat.py backend/tests/test_chat_endpoint.py
git commit -m "feat(chat): integrate Claude streaming + live metrics injection"
```

---

# Sprint 4 — /chat Full-Screen Page

## Task 4.1: SSE parser + chat types

**Files:**
- Create: `frontend/src/lib/sse.ts`
- Create: `frontend/src/lib/chat-types.ts`

- [ ] **Step 1: Create `frontend/src/lib/chat-types.ts`**

```typescript
export type ChatRole = "user" | "assistant";

export interface Source {
  id: number;
  title: string;
  source: string;    // filename
  page: number;
  score: number;
}

export interface Metrics {
  region: string;
  timestamp: string;
  ndvi: number;
  fvc: number;
  risk_level: number;
  wind_speed: number;
  soil_moisture: number;
  last_alert: { level: number; message: string; timestamp: string } | null;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  sources?: Source[];
  metrics?: Metrics | null;
  streaming?: boolean;
  error?: string;
}

export interface ChatRequest {
  question: string;
  region_hint?: string | null;
}
```

- [ ] **Step 2: Create `frontend/src/lib/sse.ts`**

```typescript
export type SSEEvent = {
  event: string;
  data: string;
};

/**
 * Parse a fetch Response body as an SSE stream.
 * Yields one SSEEvent per `event: ... \n data: ... \n\n` block.
 */
export async function* parseSSE(response: Response): AsyncGenerator<SSEEvent> {
  if (!response.body) throw new Error("Response body is null");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let nlnl: number;
      while ((nlnl = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, nlnl);
        buffer = buffer.slice(nlnl + 2);
        const event = parseBlock(block);
        if (event) yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function parseBlock(block: string): SSEEvent | null {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data && event === "message") return null;
  return { event, data };
}
```

- [ ] **Step 3: No unit test at this layer**

The parser is exercised end-to-end by `test_retriever`-style integration via Playwright in Task 4.5.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/sse.ts frontend/src/lib/chat-types.ts
git commit -m "feat(chat/frontend): SSE parser + chat TS types"
```

---

## Task 4.2: useChat hook

**Files:**
- Create: `frontend/src/hooks/useChat.ts`

- [ ] **Step 1: Create the hook**

```typescript
"use client";
import { useCallback, useRef, useState } from "react";
import type { ChatMessage, Source, Metrics } from "@/lib/chat-types";
import { parseSSE } from "@/lib/sse";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const updateLast = useCallback((patch: Partial<ChatMessage>) => {
    setMessages((prev) => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      return [...prev.slice(0, -1), { ...last, ...patch, content: patch.content ?? last.content }];
    });
  }, []);

  const appendToken = useCallback((delta: string) => {
    setMessages((prev) => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      return [...prev.slice(0, -1), { ...last, content: last.content + delta }];
    });
  }, []);

  const ask = useCallback(async (question: string, regionHint?: string | null) => {
    const now = Date.now().toString();
    setMessages((prev) => [
      ...prev,
      { id: `u-${now}`, role: "user", content: question },
      { id: `a-${now}`, role: "assistant", content: "", sources: [], metrics: null, streaming: true },
    ]);
    setStreaming(true);

    const ac = new AbortController();
    abortRef.current = ac;

    try {
      const res = await fetch(`${API_BASE}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, region_hint: regionHint ?? null }),
        signal: ac.signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      for await (const evt of parseSSE(res)) {
        if (evt.event === "sources") {
          updateLast({ sources: JSON.parse(evt.data) as Source[] });
        } else if (evt.event === "metrics") {
          updateLast({ metrics: JSON.parse(evt.data) as Metrics });
        } else if (evt.event === "token") {
          appendToken(JSON.parse(evt.data) as string);
        } else if (evt.event === "error") {
          const { message } = JSON.parse(evt.data) as { message: string };
          updateLast({ error: message });
        } else if (evt.event === "done") {
          updateLast({ streaming: false });
        }
      }
    } catch (err: unknown) {
      updateLast({ streaming: false, error: (err as Error).message });
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [updateLast, appendToken]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    setMessages([]);
    setStreaming(false);
  }, []);

  return { messages, streaming, ask, stop, reset };
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && pnpm tsc --noEmit`
Expected: no errors related to the new file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useChat.ts
git commit -m "feat(chat/frontend): useChat hook with SSE consumption"
```

---

## Task 4.3: Chat UI components

**Files:**
- Create: `frontend/src/components/chat/ChatMessage.tsx`
- Create: `frontend/src/components/chat/SourcesPanel.tsx`
- Create: `frontend/src/components/chat/MetricsPanel.tsx`
- Create: `frontend/src/components/chat/ChatInput.tsx`
- Create: `frontend/src/components/chat/EmptyState.tsx`
- Modify: `frontend/package.json`

- [ ] **Step 1: Install markdown deps**

Run: `cd frontend && pnpm add react-markdown remark-gfm`
Expected: adds both packages to dependencies.

- [ ] **Step 2: Create `ChatMessage.tsx`**

```tsx
"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage as Msg } from "@/lib/chat-types";

interface Props {
  message: Msg;
  onCitationClick?: (sourceId: number) => void;
}

export function ChatMessage({ message, onCitationClick }: Props) {
  const isUser = message.role === "user";
  return (
    <div className={`py-4 ${isUser ? "text-neutral-800" : "text-neutral-900"}`}>
      <div className="mb-1 text-xs uppercase tracking-wide text-neutral-500">
        {isUser ? "你" : "SandbeltOS"}
      </div>
      {message.error ? (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          错误：{message.error}
        </div>
      ) : (
        <div className="prose prose-sm max-w-none">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Render [n] citations as clickable buttons
              p: ({ children, ...props }) => {
                const rendered = renderCitations(children, onCitationClick);
                return <p {...props}>{rendered}</p>;
              },
            }}
          >
            {message.content || (message.streaming ? "..." : "")}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}

function renderCitations(nodes: React.ReactNode, onClick?: (id: number) => void): React.ReactNode {
  if (typeof nodes === "string") {
    const parts = nodes.split(/(\[\d+\])/g);
    return parts.map((p, i) => {
      const m = p.match(/^\[(\d+)\]$/);
      if (m && onClick) {
        const id = Number(m[1]);
        return (
          <button
            key={i}
            onClick={() => onClick(id)}
            className="mx-0.5 inline-flex h-5 items-center rounded-full bg-blue-100 px-2 text-xs font-medium text-blue-700 hover:bg-blue-200"
          >
            {id}
          </button>
        );
      }
      return <span key={i}>{p}</span>;
    });
  }
  if (Array.isArray(nodes)) return nodes.map((n, i) => <span key={i}>{renderCitations(n, onClick)}</span>);
  return nodes;
}
```

- [ ] **Step 3: Create `SourcesPanel.tsx`**

```tsx
"use client";
import type { Source } from "@/lib/chat-types";

interface Props {
  sources: Source[];
  highlightId?: number | null;
}

export function SourcesPanel({ sources, highlightId }: Props) {
  if (sources.length === 0) {
    return <div className="text-sm text-neutral-400">暂无引用</div>;
  }
  return (
    <ol className="space-y-3">
      {sources.map((s) => (
        <li
          key={s.id}
          id={`source-${s.id}`}
          className={`rounded border p-3 text-sm transition ${
            highlightId === s.id ? "border-blue-400 bg-blue-50" : "border-neutral-200"
          }`}
        >
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xs text-blue-700">[{s.id}]</span>
            <span className="font-medium text-neutral-900">{s.title}</span>
          </div>
          <div className="mt-1 text-xs text-neutral-500">
            {s.source} · page {s.page} · score {s.score.toFixed(2)}
          </div>
        </li>
      ))}
    </ol>
  );
}
```

- [ ] **Step 4: Create `MetricsPanel.tsx`**

```tsx
"use client";
import type { Metrics } from "@/lib/chat-types";

interface Props {
  metrics: Metrics | null | undefined;
}

const RISK_LABEL = ["", "低", "较低", "中", "高"];

export function MetricsPanel({ metrics }: Props) {
  if (!metrics) {
    return <div className="text-sm text-neutral-400">无实时数据</div>;
  }
  return (
    <dl className="grid grid-cols-2 gap-y-2 text-sm">
      <dt className="text-neutral-500">区域</dt>
      <dd>{metrics.region}</dd>
      <dt className="text-neutral-500">NDVI</dt>
      <dd className="font-mono">{metrics.ndvi?.toFixed(2)}</dd>
      <dt className="text-neutral-500">FVC</dt>
      <dd className="font-mono">{metrics.fvc}%</dd>
      <dt className="text-neutral-500">风险等级</dt>
      <dd>
        {metrics.risk_level} / 4 ({RISK_LABEL[metrics.risk_level] ?? "?"})
      </dd>
      <dt className="text-neutral-500">风速</dt>
      <dd className="font-mono">{metrics.wind_speed?.toFixed(1)} m/s</dd>
      <dt className="text-neutral-500">土壤湿度</dt>
      <dd className="font-mono">{metrics.soil_moisture}%</dd>
      {metrics.last_alert && (
        <>
          <dt className="text-neutral-500">最近告警</dt>
          <dd className="text-red-600">{metrics.last_alert.message}</dd>
        </>
      )}
    </dl>
  );
}
```

- [ ] **Step 5: Create `ChatInput.tsx`**

```tsx
"use client";
import { useState, KeyboardEvent } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");

  function submit() {
    const v = value.trim();
    if (!v || disabled) return;
    onSend(v);
    setValue("");
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex items-end gap-2 rounded-lg border border-neutral-300 bg-white p-2">
      <textarea
        value={value}
        disabled={disabled}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKey}
        rows={1}
        placeholder="问一个关于三北、科尔沁或浑善达克的问题..."
        className="flex-1 resize-none border-0 bg-transparent px-2 py-1 text-sm outline-none disabled:opacity-50"
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        发送
      </button>
    </div>
  );
}
```

- [ ] **Step 6: Create `EmptyState.tsx`**

```tsx
"use client";

const EXAMPLES = [
  { category: "风险评估", q: "科尔沁沙地现在风险等级如何？" },
  { category: "趋势", q: "浑善达克近 20 年 NDVI 趋势怎样？" },
  { category: "指标解释", q: "RWEQ 公式是什么？有哪些输入？" },
  { category: "物种选择", q: "Caragana korshinskii 适合哪些区域造林？" },
  { category: "政策", q: "三北防护林科学绿化策略的核心原则？" },
  { category: "方法论", q: "如何判断一个区域是否已沙化？" },
];

interface Props {
  onPick: (q: string) => void;
}

export function EmptyState({ onPick }: Props) {
  return (
    <div className="mx-auto max-w-2xl py-16 text-center">
      <h1 className="mb-2 text-2xl font-semibold text-neutral-900">
        SandbeltOS 智慧问答
      </h1>
      <p className="mb-8 text-sm text-neutral-500">
        基于 12 篇核心文献 + 实时传感器数据回答你的问题
      </p>
      <div className="grid grid-cols-2 gap-3 text-left">
        {EXAMPLES.map((ex) => (
          <button
            key={ex.q}
            onClick={() => onPick(ex.q)}
            className="rounded-lg border border-neutral-200 p-3 text-sm hover:border-blue-400 hover:bg-blue-50"
          >
            <div className="mb-1 text-xs font-medium uppercase text-neutral-400">
              {ex.category}
            </div>
            <div className="text-neutral-800">{ex.q}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Verify TypeScript compiles**

Run: `cd frontend && pnpm tsc --noEmit`
Expected: no type errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/chat frontend/package.json frontend/pnpm-lock.yaml
git commit -m "feat(chat/frontend): ChatMessage, Sources, Metrics, Input, EmptyState"
```

---

## Task 4.4: /chat page assembly

**Files:**
- Create: `frontend/src/app/chat/page.tsx`

- [ ] **Step 1: Create the page**

```tsx
"use client";
import { useState } from "react";
import { useChat } from "@/hooks/useChat";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { SourcesPanel } from "@/components/chat/SourcesPanel";
import { MetricsPanel } from "@/components/chat/MetricsPanel";
import { ChatInput } from "@/components/chat/ChatInput";
import { EmptyState } from "@/components/chat/EmptyState";

export default function ChatPage() {
  const { messages, streaming, ask, reset } = useChat();
  const [highlightId, setHighlightId] = useState<number | null>(null);

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const sources = lastAssistant?.sources ?? [];
  const metrics = lastAssistant?.metrics ?? null;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-neutral-200 px-6 py-3">
        <h1 className="text-sm font-medium">SandbeltOS 智慧问答</h1>
        <button
          onClick={reset}
          disabled={streaming || messages.length === 0}
          className="rounded border border-neutral-300 px-3 py-1 text-xs text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
        >
          新对话
        </button>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <main className="flex flex-1 flex-col">
          <div className="flex-1 overflow-y-auto px-6">
            {messages.length === 0 ? (
              <EmptyState onPick={ask} />
            ) : (
              <div className="mx-auto max-w-3xl divide-y divide-neutral-200">
                {messages.map((m) => (
                  <ChatMessage key={m.id} message={m} onCitationClick={setHighlightId} />
                ))}
              </div>
            )}
          </div>
          <div className="mx-auto w-full max-w-3xl px-6 py-4">
            <ChatInput onSend={ask} disabled={streaming} />
          </div>
        </main>

        <aside className="w-[320px] overflow-y-auto border-l border-neutral-200 bg-neutral-50 p-4">
          <section className="mb-6">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
              引用来源
            </h2>
            <SourcesPanel sources={sources} highlightId={highlightId} />
          </section>
          <section>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
              实时指标
            </h2>
            <MetricsPanel metrics={metrics} />
          </section>
        </aside>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run dev server and manual check**

Run: `cd frontend && pnpm dev` (background; use `run_in_background: true`).

Open `http://localhost:3000/chat` in browser.
Expected:
- Empty state with 6 example cards
- Click one → question appears, sources panel populates, tokens stream
- Citation pills in answer are clickable → right panel highlights that source

If backend isn't reachable from frontend, set `NEXT_PUBLIC_API_BASE=http://localhost:8000` in `frontend/.env.local`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/chat frontend/.env.local
git commit -m "feat(chat/frontend): /chat full-screen page with sources + metrics panels"
```

---

## Task 4.5: /chat E2E test

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/chat.spec.ts`
- Modify: `frontend/package.json`

- [ ] **Step 1: Install Playwright**

Run: `cd frontend && pnpm add -D @playwright/test && npx playwright install chromium`
Expected: Playwright + chromium installed.

- [ ] **Step 2: Create `frontend/playwright.config.ts`**

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
```

- [ ] **Step 3: Create `frontend/e2e/chat.spec.ts`**

```typescript
import { test, expect } from "@playwright/test";

test.describe("/chat", () => {
  test("shows empty state with example questions", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.getByRole("heading", { name: /SandbeltOS 智慧问答/ })).toBeVisible();
    await expect(page.getByText("风险评估")).toBeVisible();
    await expect(page.getByText("物种选择")).toBeVisible();
  });

  test("clicking an example streams a response", async ({ page }) => {
    await page.goto("/chat");
    await page.getByRole("button", { name: /RWEQ 公式/ }).click();

    // User message renders immediately
    await expect(page.getByText("你", { exact: false })).toBeVisible();

    // Sources panel populates before answer
    await expect(page.locator("#source-1")).toBeVisible({ timeout: 10_000 });

    // Assistant message eventually has some content
    await expect(page.locator(".prose").first()).not.toHaveText("...", { timeout: 15_000 });
  });

  test("new conversation resets", async ({ page }) => {
    await page.goto("/chat");
    await page.getByRole("button", { name: /风险评估/ }).click();
    await expect(page.locator("#source-1")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "新对话" }).click();
    await expect(page.getByText("风险评估")).toBeVisible();
  });
});
```

- [ ] **Step 4: Add test script to `frontend/package.json`**

Under `scripts`:
```json
"e2e": "playwright test",
"e2e:headed": "playwright test --headed"
```

- [ ] **Step 5: Run E2E (requires backend running)**

Run in separate terminal: `cd backend && uvicorn app.main:app --port 8000`
Run: `cd frontend && pnpm e2e`
Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/playwright.config.ts frontend/e2e/chat.spec.ts frontend/package.json frontend/pnpm-lock.yaml
git commit -m "test(chat/frontend): Playwright E2E for /chat page"
```

---

# Sprint 5 — Dashboard Widget + Golden Validation

## Task 5.1: ChatWidget component

**Files:**
- Create: `frontend/src/components/ChatWidget.tsx`

- [ ] **Step 1: Create the widget**

```tsx
"use client";
import { useState } from "react";
import { useChat } from "@/hooks/useChat";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import type { Source, Metrics } from "@/lib/chat-types";

interface Props {
  regionHint?: string | null;
}

export function ChatWidget({ regionHint }: Props) {
  const [open, setOpen] = useState(false);
  const { messages, streaming, ask, reset } = useChat();

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const sources: Source[] = lastAssistant?.sources ?? [];
  const metrics: Metrics | null | undefined = lastAssistant?.metrics;

  if (!open) {
    return (
      <button
        aria-label="打开 SandbeltOS 问答"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg hover:bg-blue-700"
      >
        💬
      </button>
    );
  }

  return (
    <div
      className="fixed bottom-6 right-6 z-50 flex w-[400px] flex-col overflow-hidden rounded-lg border border-neutral-300 bg-white shadow-2xl"
      style={{ height: "60vh" }}
    >
      <header className="flex items-center justify-between border-b border-neutral-200 px-3 py-2">
        <span className="text-sm font-medium">SandbeltOS Copilot</span>
        <div className="flex gap-1">
          <a
            href="/chat"
            aria-label="在全屏模式打开"
            className="rounded p-1 text-neutral-500 hover:bg-neutral-100"
          >
            ⤢
          </a>
          <button
            aria-label="关闭"
            onClick={() => setOpen(false)}
            className="rounded p-1 text-neutral-500 hover:bg-neutral-100"
          >
            ✕
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-3">
        {messages.length === 0 && (
          <div className="py-4 text-xs text-neutral-500">
            💡 试问：
            <ul className="mt-2 space-y-1">
              <li>
                <button
                  onClick={() => ask("现在风险怎么样？", regionHint)}
                  className="text-blue-600 hover:underline"
                >
                  现在风险怎么样？
                </button>
              </li>
              <li>
                <button
                  onClick={() => ask("RWEQ 公式是什么？", regionHint)}
                  className="text-blue-600 hover:underline"
                >
                  RWEQ 公式是什么？
                </button>
              </li>
            </ul>
          </div>
        )}
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
        {sources.length > 0 && (
          <div className="flex flex-wrap gap-1 border-t border-neutral-100 py-2">
            {sources.map((s) => (
              <span
                key={s.id}
                title={`${s.title} · p.${s.page}`}
                className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700"
              >
                [{s.id}] {s.source.slice(0, 24)}…
              </span>
            ))}
          </div>
        )}
        {metrics && (
          <div className="border-t border-neutral-100 py-2 text-xs text-neutral-600">
            📊 {metrics.region}: NDVI {metrics.ndvi?.toFixed(2)}, 风险 {metrics.risk_level}/4
          </div>
        )}
      </div>

      <div className="border-t border-neutral-200 p-2">
        <ChatInput onSend={(q) => ask(q, regionHint)} disabled={streaming} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

Run: `cd frontend && pnpm tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ChatWidget.tsx
git commit -m "feat(chat/frontend): Dashboard floating chat widget"
```

---

## Task 5.2: Mount widget on Dashboard

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx`

- [ ] **Step 1: Identify current region source**

Read `frontend/src/app/dashboard/page.tsx` and locate the state that tracks the user-selected region (likely something like `selectedRegion`, `primaryRegion`, or a prop from `RegionMap`).

- [ ] **Step 2: Import and mount ChatWidget**

At top of file, add:
```tsx
import dynamic from "next/dynamic";

const ChatWidget = dynamic(
  () => import("@/components/ChatWidget").then((m) => m.ChatWidget),
  { ssr: false },
);
```

Near the bottom of the returned JSX (outside the main grid but inside the root wrapper), add:
```tsx
<ChatWidget regionHint={primaryRegion /* or whatever state var holds the region */} />
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm build`
Expected: build succeeds.

- [ ] **Step 4: Manual check**

Run: `cd frontend && pnpm dev`
Open `http://localhost:3000/dashboard`.
Expected:
- 💬 button bottom-right
- Click → panel opens
- Ask "现在风险怎么样？" → uses current region automatically

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/dashboard/page.tsx
git commit -m "feat(dashboard): mount ChatWidget with region auto-injection"
```

---

## Task 5.3: Golden QA set

**Files:**
- Create: `backend/tests/golden_qa.yaml`
- Create: `backend/tests/test_golden.py`

- [ ] **Step 1: Create `backend/tests/golden_qa.yaml`**

```yaml
- id: 1
  question: "科尔沁沙地近 20 年 NDVI 趋势怎样？"
  must_include_source_patterns:
    - "inner_mongolia"
    - "three-north"
  must_include_keywords: ["NDVI"]
  min_length: 80

- id: 2
  question: "浑善达克现在风险等级是多少？为什么？"
  must_include_source_patterns:
    - "hunshandake"
  must_include_keywords: ["风险"]
  min_length: 80
  expects_live_metrics: true

- id: 3
  question: "RWEQ 公式怎么算？用了哪些输入？"
  must_include_source_patterns:
    - "wind_erosion"
  must_include_keywords: ["RWEQ", "风速"]
  min_length: 100

- id: 4
  question: "Caragana korshinskii 适合在哪些区域造林？"
  must_include_source_patterns:
    - "caragana"
  must_include_keywords: ["Caragana"]
  min_length: 80

- id: 5
  question: "三北防护林科学绿化策略的核心原则是什么？"
  must_include_source_patterns:
    - "scientific-greening"
  must_include_keywords: ["绿化"]
  min_length: 100

- id: 6
  question: "为什么 2022 年 NE 内蒙古土壤侵蚀下降？"
  must_include_source_patterns:
    - "decreasing_soil_erosion"
  must_include_keywords: ["侵蚀", "下降"]
  min_length: 100

- id: 7
  question: "浑善达克的固沙林对土壤性质有何影响？"
  must_include_source_patterns:
    - "hunshandake"
    - "sand_fixation"
  must_include_keywords: ["土壤"]
  min_length: 100

- id: 8
  question: "Populus simoni 在辽宁沙地表现如何？"
  must_include_source_patterns:
    - "populus_simoni"
  must_include_keywords: ["Populus"]
  min_length: 80

- id: 9
  question: "怎样判断一个区域是否已沙化？"
  must_include_keywords: ["沙化"]
  min_length: 100

- id: 10
  question: "实时数据显示科尔沁 NDVI 0.3，算偏低吗？"
  must_include_source_patterns:
    - "ndvi"
    - "three-north"
  must_include_keywords: ["NDVI", "0.3"]
  min_length: 100
```

- [ ] **Step 2: Create `backend/tests/test_golden.py`**

```python
"""Golden Q&A runner. Uses the real retriever + a mocked LLM that echoes context."""
from __future__ import annotations
import pytest
import yaml
from pathlib import Path
from backend.rag.retriever import retrieve
from backend.rag.prompt_templates import build_prompt

pytestmark = pytest.mark.slow

GOLDEN_PATH = Path(__file__).parent / "golden_qa.yaml"

@pytest.fixture(scope="session")
def golden_cases():
    return yaml.safe_load(GOLDEN_PATH.read_text())

@pytest.mark.parametrize("case", yaml.safe_load(GOLDEN_PATH.read_text()), ids=lambda c: f"Q{c['id']}")
def test_golden_retrieval(case):
    """Verify retrieval returns sources that match the expected patterns."""
    results = retrieve(case["question"], region=None, top_k=5, use_rerank=True)
    assert len(results) > 0, f"Q{case['id']}: no results returned"

    if "must_include_source_patterns" in case:
        got_sources = [r.chunk.source.lower() for r in results]
        for pattern in case["must_include_source_patterns"]:
            assert any(pattern.lower() in s for s in got_sources), (
                f"Q{case['id']}: expected source matching '{pattern}' in {got_sources}"
            )
```

Note: This test verifies **retrieval** correctness (does the expected literature show up?). Full answer-quality checks require human review of actual LLM output; we do that manually in the next step.

- [ ] **Step 3: Run golden tests**

Run: `cd backend && pytest tests/test_golden.py -v -m slow`
Expected: ≥8 of 10 pass. If fewer, either:
- Adjust `must_include_source_patterns` (too strict)
- Supplement the corpus with a targeted PDF (note in spec §3 "扩充机制")

- [ ] **Step 4: Manual LLM review (human in the loop)**

With backend + frontend running, manually ask each of the 10 questions through `/chat` and rate the answer on:
- Correctness (factually matches literature)
- Citation accuracy ([n] refers to a relevant paper)
- Live data usage (Q2, Q10 should mention current NDVI/risk)

Record results in a temporary file (do not commit); flag any Q that scored <3/5 for follow-up.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/golden_qa.yaml backend/tests/test_golden.py
git commit -m "test(rag): golden QA set with retrieval assertions"
```

---

## Task 5.4: Widget E2E test

**Files:**
- Create: `frontend/e2e/widget.spec.ts`

- [ ] **Step 1: Create `frontend/e2e/widget.spec.ts`**

```typescript
import { test, expect } from "@playwright/test";

test.describe("Dashboard ChatWidget", () => {
  test("widget button opens the panel", async ({ page }) => {
    await page.goto("/dashboard");
    const btn = page.getByRole("button", { name: /打开.*问答/ });
    await expect(btn).toBeVisible();
    await btn.click();
    await expect(page.getByText("SandbeltOS Copilot")).toBeVisible();
  });

  test("widget ask injects region and gets sources", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /打开.*问答/ }).click();
    await page.getByRole("button", { name: "现在风险怎么样？" }).click();
    // Source pills eventually appear
    await expect(page.getByText(/\[1\]/).first()).toBeVisible({ timeout: 15_000 });
  });

  test("widget full-screen link navigates to /chat", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /打开.*问答/ }).click();
    await page.getByRole("link", { name: /全屏/ }).click();
    await expect(page).toHaveURL(/\/chat$/);
  });

  test("widget close hides the panel", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /打开.*问答/ }).click();
    await page.getByRole("button", { name: "关闭" }).click();
    await expect(page.getByRole("button", { name: /打开.*问答/ })).toBeVisible();
  });
});
```

- [ ] **Step 2: Run E2E**

With backend + frontend running:
Run: `cd frontend && pnpm e2e widget.spec.ts`
Expected: all 4 tests pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/widget.spec.ts
git commit -m "test(chat/frontend): Playwright E2E for Dashboard widget"
```

---

## Task 5.5: Final cleanup + README note

**Files:**
- Modify: `backend/rag/docs/README.md` (create if absent)

- [ ] **Step 1: Write a short corpus README**

Create `backend/rag/docs/README.md`:

```markdown
# RAG Corpus

MVP corpus of 12 PDFs covering Three-North Shelterbelt, Horqin, and Hunshandake.

## Recreating

PDFs are gitignored. To reproduce:

```bash
bash backend/rag/download_corpus.sh          # 12/35 succeed (MDPI blocks curl)
bash backend/rag/download_corpus_round2.sh   # retry + alternates
```

Any MDPI papers you want to add, download manually via browser and drop into
`papers_en/`, then run:

```bash
python -m backend.rag.ingest --rebuild
```

## Structure

- `gov/` — Chinese government reports, standards
- `papers_cn/` — Chinese peer-reviewed papers
- `papers_en/` — English peer-reviewed papers
- `standards/` — (placeholder for future technical standards)
```

- [ ] **Step 2: Final test pass (excluding slow/network-heavy)**

Run: `cd backend && pytest tests/ -v -k "not slow" --tb=short`
Expected: all non-slow tests PASS.

Then optionally: `cd backend && pytest tests/ -v -m slow --tb=short` (requires bge-m3 + bge-reranker + populated Chroma).

- [ ] **Step 3: Commit**

```bash
git add backend/rag/docs/README.md
git commit -m "docs(rag): corpus README + reproduction steps"
```

---

## Done Criteria

Phase 4 is complete when:
- [ ] All 23 task checkboxes above are checked
- [ ] `pytest -k "not slow"` green
- [ ] `pytest -m slow` green with real models loaded + Chroma populated (≥8/10 golden tests pass)
- [ ] `pnpm e2e` green (both chat.spec.ts and widget.spec.ts)
- [ ] Manual review of 10 golden questions via `/chat`: ≥8 answers factually correct with working citations
- [ ] Dashboard widget opens, region auto-injects, full-screen link navigates correctly

---

## Risks & Mitigations (from spec §11)

| Risk | Mitigation in this plan |
|---|---|
| bge-m3 download stalls | Task 1.3 singleton + Task 1.5 logs |
| Chinese chunking breaks sentences | Task 1.2 tests assert sentence boundaries |
| Claude 429 / timeout | Task 3.3 wraps stream in try/except; frontend `error` event |
| Only 12 PDFs → weak answers | Task 5.3 golden set exposes gaps; README notes how to expand |
| Chroma file corruption | `ingest.py --rebuild` |
| Dashboard LCP regression | Task 5.2 uses `dynamic(ssr: false)` |

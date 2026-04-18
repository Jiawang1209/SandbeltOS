"""Core dataclasses for the RAG pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Chunk:
    text: str
    source: str  # filename, e.g. "2024_hunshandake_sand_fixation.pdf"
    title: str
    category: Literal["gov", "papers_cn", "papers_en", "standards"]
    page: int
    lang: Literal["zh", "en"]
    region_hint: list[str] = field(default_factory=list)  # ["horqin", "hunshandake", ...]
    chunk_id: str = ""  # f"{source}#p{page}#c{idx}"


@dataclass
class SearchResult:
    chunk: Chunk
    score: float  # post-rerank if reranked, else dense similarity


@dataclass
class QueryContext:
    regions: list[str]
    intents: list[str]
    needs_live_data: bool

"""PDF → Chunk[] text extraction + Chinese-friendly splitting.

Pure text utilities plus a PyMuPDF-backed PDF reader. Kept free of
embedding / storage concerns so tests can exercise splitting without
model downloads.
"""
from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.types import Chunk

_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")

# Region aliases include English names, transliterations, and primary
# Chinese forms. Matched case-insensitively against filename + title.
_REGION_ALIASES: dict[str, list[str]] = {
    "horqin": ["horqin", "korqin", "科尔沁", "通辽", "奈曼"],
    "hunshandake": ["hunshandake", "otindag", "浑善达克", "锡林郭勒"],
}


def detect_lang(text: str) -> str:
    """Classify a text blob as 'zh' or 'en' by CJK density."""
    chinese = len(_CHINESE_CHAR_RE.findall(text))
    # Either absolute CJK count ≥ 20, or ≥10% of total chars — whichever
    # triggers first. English-only strings fall through to 'en'.
    if chinese >= 20 or (text and chinese / max(len(text), 1) >= 0.1):
        return "zh"
    return "en"


def detect_region_hints(filename: str, title: str) -> list[str]:
    """Match configured region aliases against filename + title."""
    haystack = f"{filename} {title}".lower()
    return [
        region
        for region, aliases in _REGION_ALIASES.items()
        if any(alias.lower() in haystack for alias in aliases)
    ]


def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[str]:
    """Split raw text into overlapping chunks with Chinese-friendly separators."""
    if not text or not text.strip():
        return []
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
    """Extract text page-by-page from a PDF and split into Chunks."""
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
            chunks.append(
                Chunk(
                    text=piece,
                    source=path.name,
                    title=display_title,
                    category=category,  # type: ignore[arg-type]
                    page=page_idx,
                    lang=lang,  # type: ignore[arg-type]
                    region_hint=region_hints,
                    chunk_id=f"{path.name}#p{page_idx}#c{c_idx}",
                )
            )
    doc.close()
    return chunks

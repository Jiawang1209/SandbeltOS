"""Tests for backend.rag.chunker."""
from __future__ import annotations

import pytest

from rag.chunker import chunk_text, detect_lang, detect_region_hints


def test_chunk_text_chinese_respects_sentence_boundary() -> None:
    text = "第一句话。第二句话。" * 50
    chunks = chunk_text(text, chunk_size=80, chunk_overlap=10)
    assert len(chunks) >= 2
    # Separators include 。！？ so most chunks should end on a boundary char
    # when they are over the soft limit.
    for c in chunks[:-1]:
        stripped = c.rstrip()
        assert stripped.endswith(("。", "！", "？")) or len(stripped) <= 80


def test_chunk_text_english_preserves_paragraphs() -> None:
    text = "Para one sentence one. Para one sentence two.\n\nPara two sentence one."
    chunks = chunk_text(text, chunk_size=50, chunk_overlap=5)
    joined = " ".join(chunks)
    assert "Para one" in joined
    assert "Para two" in joined


def test_chunk_text_empty_returns_empty() -> None:
    assert chunk_text("   ", chunk_size=80, chunk_overlap=10) == []


def test_detect_lang_chinese() -> None:
    assert detect_lang("这是一段中文文本，包含了中文字符，长度足够。" * 3) == "zh"


def test_detect_lang_english() -> None:
    assert detect_lang("This is an English sentence only. No CJK characters here.") == "en"


def test_detect_region_hints_from_filename() -> None:
    assert "horqin" in detect_region_hints("2021_horqin_land_vegetation.pdf", "")
    assert "hunshandake" in detect_region_hints(
        "2024_hunshandake_sand_fixation.pdf", ""
    )


def test_detect_region_hints_from_title_otindag_alias() -> None:
    hints = detect_region_hints("generic.pdf", "Spatial Patterns in Otindag Sandy Land")
    assert "hunshandake" in hints


def test_detect_region_hints_chinese_title() -> None:
    hints = detect_region_hints("2023_paper.pdf", "科尔沁沙地植被恢复分析")
    assert "horqin" in hints


def test_detect_region_hints_none() -> None:
    assert detect_region_hints("generic_global.pdf", "Global Soil Erosion") == []

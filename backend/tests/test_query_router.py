"""Tests for app.services.query_router.

Pure-Python keyword router, no model downloads. Fast.
"""
from __future__ import annotations


def test_parse_horqin_current_status() -> None:
    from app.services.query_router import parse

    ctx = parse("科尔沁现在风险怎样")
    assert "horqin" in ctx.regions
    assert "current_status" in ctx.intents
    assert "risk" in ctx.intents
    assert ctx.needs_live_data is True


def test_parse_hunshandake_trend() -> None:
    from app.services.query_router import parse

    ctx = parse("浑善达克近 20 年 NDVI 趋势")
    assert "hunshandake" in ctx.regions
    assert "trend" in ctx.intents
    assert ctx.needs_live_data is True


def test_parse_method_question_no_live() -> None:
    from app.services.query_router import parse

    ctx = parse("RWEQ 公式怎么算")
    assert ctx.regions == []
    assert "method" in ctx.intents
    assert ctx.needs_live_data is False


def test_parse_species_question_with_region_no_live() -> None:
    from app.services.query_router import parse

    ctx = parse("科尔沁适合什么树种")
    assert "horqin" in ctx.regions
    assert "species" in ctx.intents
    # species is research-oriented; live data reserved for status/risk/trend
    assert ctx.needs_live_data is False


def test_parse_otindag_alias_maps_to_hunshandake() -> None:
    from app.services.query_router import parse

    ctx = parse("Otindag desertification now")
    assert "hunshandake" in ctx.regions
    assert "current_status" in ctx.intents


def test_parse_empty_query() -> None:
    from app.services.query_router import parse

    ctx = parse("")
    assert ctx.regions == []
    assert ctx.intents == []
    assert ctx.needs_live_data is False

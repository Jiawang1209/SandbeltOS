"""Keyword-based query router: text → QueryContext(regions, intents, needs_live_data).

Intentionally dumb and deterministic. Region aliases mirror rag.chunker to
keep retrieval filter and prompt routing consistent. Intent patterns are
tuned for the 12-PDF MVP corpus; add categories sparingly.

`needs_live_data` is True only when the query both names a region AND asks
about current/trend/risk — pure research questions ("RWEQ 公式怎么算") stay
corpus-only.
"""
from __future__ import annotations

import re

from rag.types import QueryContext

REGION_KEYWORDS: dict[str, list[str]] = {
    "horqin": ["科尔沁", "Horqin", "horqin", "Korqin", "通辽", "奈曼"],
    "hunshandake": ["浑善达克", "Hunshandake", "Otindag", "otindag", "锡林郭勒"],
}

INTENT_PATTERNS: dict[str, list[str]] = {
    "current_status": [r"现在", r"当前", r"目前", r"\bnow\b", r"\bcurrent\b"],
    "trend": [r"趋势", r"变化", r"近\s*\d+\s*年", r"\btrend\b", r"\bchange\b"],
    "risk": [r"风险", r"危险", r"\brisk\b", r"\balert\b", r"沙化", r"退化", r"desertification"],
    "species": [r"树种", r"植被", r"造林", r"\bspecies\b", r"\bplantation\b"],
    "method": [r"怎么算", r"公式", r"方法", r"RWEQ", r"FVC", r"NDVI.*计算", r"how.*calculate"],
    "policy": [r"规划", r"政策", r"战略", r"工程", r"\bpolicy\b"],
}

LIVE_DATA_INTENTS: frozenset[str] = frozenset({"current_status", "risk", "trend"})


def _match_regions(query: str) -> list[str]:
    q_lower = query.lower()
    return [
        region
        for region, aliases in REGION_KEYWORDS.items()
        if any(a.lower() in q_lower for a in aliases)
    ]


def _match_intents(query: str) -> list[str]:
    hits: list[str] = []
    for intent, patterns in INTENT_PATTERNS.items():
        if any(re.search(pat, query, flags=re.IGNORECASE) for pat in patterns):
            hits.append(intent)
    return hits


def parse(query: str) -> QueryContext:
    regions = _match_regions(query)
    intents = _match_intents(query)
    needs_live = bool(regions) and bool(set(intents) & LIVE_DATA_INTENTS)
    return QueryContext(regions=regions, intents=intents, needs_live_data=needs_live)

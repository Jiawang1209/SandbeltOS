"""Golden Q&A retrieval assertions.

Verifies the retriever surfaces expected literature for each canonical question.
Does NOT check LLM answer quality — that requires human review (see plan §5.3
Step 4). Marked `slow` because it loads the embedding model and FAISS index.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rag.retriever import retrieve

pytestmark = pytest.mark.slow

GOLDEN_PATH = Path(__file__).parent / "golden_qa.yaml"
_CASES = yaml.safe_load(GOLDEN_PATH.read_text())


@pytest.mark.parametrize("case", _CASES, ids=lambda c: f"Q{c['id']}")
def test_golden_retrieval(case):
    results = retrieve(case["question"], region=None, top_k=5, use_rerank=True)
    assert len(results) > 0, f"Q{case['id']}: no results returned"

    if "must_include_source_patterns" in case:
        got_sources = [r.chunk.source.lower() for r in results]
        for pattern in case["must_include_source_patterns"]:
            assert any(pattern.lower() in s for s in got_sources), (
                f"Q{case['id']}: expected source matching '{pattern}' in {got_sources}"
            )

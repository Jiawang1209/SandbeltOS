"""Offline RAG retrieval quality eval.

Loads `tests/golden_qa.yaml`, runs the two-stage retriever for each
question, and prints a markdown report:

  - recall@1 / @3 / @5: did any top-K chunk's source filename match an
    expected `must_include_source_patterns` entry?
  - MRR (mean reciprocal rank): 1/rank of the first matching source in
    top-5; 0 if no match. Reported as the mean across questions.
  - keyword_coverage: fraction of `must_include_keywords` (case-
    insensitive substring) that appear anywhere in the concatenated text
    of the top-5 retrieved chunks.
  - Per-category breakdown by Chunk.category (gov / papers_cn /
    papers_en / standards) — counts how often each category was the
    first matching hit, so we can see which doc type is doing the heavy
    lifting.

No LLM call, no DB, no network — runs against the existing
chroma_store with the embedder + reranker already on disk.

Usage:
    python -m scripts.eval_rag                       # markdown to stdout
    python -m scripts.eval_rag --out eval_report.md  # also write to file
    python -m scripts.eval_rag --no-rerank           # dense-only baseline
    python -m scripts.eval_rag --top-k 10            # widen the window
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Make the script importable as `python -m scripts.eval_rag` from backend/.
# The actual rag.retriever import is deferred until run-time so --help works
# even when the full backend env (pydantic-settings / chromadb / etc.) isn't
# installed — handy for CI smoke checks.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

GOLDEN_PATH = _BACKEND_ROOT / "tests" / "golden_qa.yaml"


@dataclass
class QuestionResult:
    qid: int
    question: str
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    rr: float  # reciprocal rank (0 if no hit in top-K)
    keyword_coverage: float  # fraction of expected keywords found in top-K text
    first_hit_category: str | None  # category of the first matching chunk, if any
    expected_patterns: list[str]
    top_sources: list[str]


def _source_matches(source: str, patterns: list[str]) -> bool:
    s = source.lower()
    return any(p.lower() in s for p in patterns)


def _first_hit_rank(results: list[Any], patterns: list[str]) -> int | None:
    """1-based index of the first chunk whose source matches any pattern."""
    for i, r in enumerate(results, start=1):
        if _source_matches(r.chunk.source, patterns):
            return i
    return None


def evaluate(case: dict[str, Any], top_k: int, use_rerank: bool) -> QuestionResult:
    # Local import — see module-level comment for why this is deferred.
    from rag.retriever import retrieve  # noqa: PLC0415

    results = retrieve(
        case["question"],
        region=None,
        top_k=top_k,
        use_rerank=use_rerank,
    )

    patterns: list[str] = case.get("must_include_source_patterns") or []
    keywords: list[str] = case.get("must_include_keywords") or []

    # Source-pattern metrics — only meaningful when the case declares patterns.
    if patterns:
        hit1 = float(any(_source_matches(r.chunk.source, patterns) for r in results[:1]))
        hit3 = float(any(_source_matches(r.chunk.source, patterns) for r in results[:3]))
        hit5 = float(any(_source_matches(r.chunk.source, patterns) for r in results[:5]))
        rank = _first_hit_rank(results, patterns)
        rr = 1.0 / rank if rank else 0.0
        first_hit = (
            results[rank - 1].chunk.category if rank and rank <= len(results) else None
        )
    else:
        hit1 = hit3 = hit5 = float("nan")
        rr = float("nan")
        first_hit = None

    # Keyword coverage — substring search in concatenated top-K text.
    if keywords:
        blob = " ".join(r.chunk.text for r in results).lower()
        found = sum(1 for kw in keywords if kw.lower() in blob)
        kw_cov = found / len(keywords)
    else:
        kw_cov = float("nan")

    return QuestionResult(
        qid=case["id"],
        question=case["question"],
        recall_at_1=hit1,
        recall_at_3=hit3,
        recall_at_5=hit5,
        rr=rr,
        keyword_coverage=kw_cov,
        first_hit_category=first_hit,
        expected_patterns=patterns,
        top_sources=[r.chunk.source for r in results[:5]],
    )


def _fmt(x: float) -> str:
    return "—" if x != x else f"{x:.2f}"  # NaN check: NaN != NaN


def _mean(xs: list[float]) -> float:
    valid = [v for v in xs if v == v]  # drop NaN
    return sum(valid) / len(valid) if valid else float("nan")


def format_report(
    rows: list[QuestionResult],
    top_k: int,
    use_rerank: bool,
) -> str:
    lines: list[str] = []
    mode = "rerank" if use_rerank else "dense-only"
    lines.append(f"# RAG Retrieval Eval ({mode}, top_k={top_k})")
    lines.append("")
    lines.append(f"Cases: {len(rows)}  ·  golden file: `tests/golden_qa.yaml`")
    lines.append("")

    # Per-question table.
    lines.append("## Per question")
    lines.append("")
    lines.append("| Q | recall@1 | recall@3 | recall@5 | RR | kw cov | first hit | expected pattern |")
    lines.append("|---|----------|----------|----------|----|--------|-----------|------------------|")
    for r in rows:
        patt = ", ".join(r.expected_patterns) if r.expected_patterns else "—"
        cat = r.first_hit_category or "—"
        lines.append(
            f"| {r.qid} | {_fmt(r.recall_at_1)} | {_fmt(r.recall_at_3)} | "
            f"{_fmt(r.recall_at_5)} | {_fmt(r.rr)} | {_fmt(r.keyword_coverage)} | "
            f"{cat} | `{patt}` |"
        )

    # Aggregates.
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("|--------|-------|")
    lines.append(f"| mean recall@1 | {_fmt(_mean([r.recall_at_1 for r in rows]))} |")
    lines.append(f"| mean recall@3 | {_fmt(_mean([r.recall_at_3 for r in rows]))} |")
    lines.append(f"| mean recall@5 | {_fmt(_mean([r.recall_at_5 for r in rows]))} |")
    lines.append(f"| MRR (top-{top_k}) | {_fmt(_mean([r.rr for r in rows]))} |")
    lines.append(
        f"| mean keyword coverage | {_fmt(_mean([r.keyword_coverage for r in rows]))} |"
    )

    # Per-category breakdown of "first matching hit".
    by_cat: dict[str, int] = {}
    for r in rows:
        cat = r.first_hit_category or "(no hit)"
        by_cat[cat] = by_cat.get(cat, 0) + 1
    lines.append("")
    lines.append("## First-hit by category")
    lines.append("")
    lines.append("| category | count |")
    lines.append("|----------|-------|")
    for cat, n in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {cat} | {n} |")

    # Per-question top-5 sources for debugging poor hits.
    lines.append("")
    lines.append("## Top-5 sources per question (debug)")
    lines.append("")
    for r in rows:
        marker = "❌" if r.expected_patterns and r.recall_at_5 == 0 else "✓"
        lines.append(f"- {marker} **Q{r.qid}** _{r.question}_")
        for i, src in enumerate(r.top_sources, start=1):
            lines.append(f"  {i}. `{src}`")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Skip the bge-reranker (dense-only baseline).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output path. Report always also prints to stdout.",
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=GOLDEN_PATH,
        help=f"Path to golden Q&A yaml (default: {GOLDEN_PATH}).",
    )
    args = parser.parse_args()

    cases = yaml.safe_load(args.golden.read_text())
    rows = [
        evaluate(case, top_k=args.top_k, use_rerank=not args.no_rerank)
        for case in cases
    ]

    report = format_report(rows, top_k=args.top_k, use_rerank=not args.no_rerank)
    print(report)
    if args.out:
        args.out.write_text(report)
        print(f"[wrote {args.out}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

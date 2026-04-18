"""Prompt templates for the RAG chat endpoint.

Pure rendering — no I/O, no LLM calls. Consumed by `app.api.v1.chat` which
wires retrieval results + live-metrics snapshot into the final prompt sent
to Claude. Kept in `rag/` (not `app/`) so non-HTTP callers (CLI, evals)
can reuse the same formatting.
"""
from __future__ import annotations

from typing import Any

from rag.types import SearchResult

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
    """Number sources from 1 so `[n]` citations line up with the SSE sources payload."""
    lines: list[str] = []
    for i, r in enumerate(results, start=1):
        lines.append(f"[{i}] {r.chunk.title} (page {r.chunk.page}, {r.chunk.source})")
        lines.append(r.chunk.text.strip())
        lines.append("")
    return "\n".join(lines).strip()


def render_metrics_block(snapshot: dict[str, Any] | None) -> str:
    if snapshot is None:
        return "(实时数据不可用)"
    alert = snapshot.get("last_alert")
    if alert:
        alert_str = (
            f"最近告警: {alert.get('message')} "
            f"(severity {alert.get('severity') or alert.get('level')})"
        )
    else:
        alert_str = "最近告警: 无"
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
    """SSE-ready sources metadata keyed 1..N to mirror the prompt's `[n]` citations."""
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

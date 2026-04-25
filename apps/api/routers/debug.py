"""
Runtime debug endpoints — diagnostics only, never expose publicly in production.
"""

from __future__ import annotations

from fastapi import APIRouter

from apps.api.models.session import ChatMessage
from apps.api.services import orchestrator, session_store

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/timings")
async def timings(
    q: str = "أبي شي حار وغير غالي",
    follow_up: str | None = None,
) -> dict:
    """
    One-shot end-to-end timing probe using the real orchestrator build + stream path.

    Usage:
      curl 'http://localhost:8001/debug/timings'
      curl 'http://localhost:8001/debug/timings?q=وش عندكم من المشاوي؟'
      curl 'http://localhost:8001/debug/timings?q=أبي شي حار&follow_up=وش الأرخص؟'
    """
    session = session_store.create_session()
    first_pass = await orchestrator.collect_benchmark(session.session_id, q)

    report: dict = {
        "query": q,
        "route": first_pass["route"],
        "rag_used": first_pass["rag_used"],
        "backend": first_pass["backend"],
        "model": first_pass["model"],
        "history_chars": first_pass["history_chars"],
        "prompt_chars": first_pass["prompt_chars"],
        "history_load_ms": first_pass["history_load_ms"],
        "prompt_build_ms": first_pass["prompt_build_ms"],
        "embed_ms": first_pass.get("embed_ms", 0.0),
        "qdrant_ms": first_pass.get("qdrant_ms", 0.0),
        "rag_search_ms": first_pass.get("rag_search_ms", 0.0),
        "llm_ttft_ms": first_pass["llm_ttft_ms"],
        "llm_decode_ms": first_pass["llm_decode_ms"],
        "llm_total_ms": first_pass["llm_total_ms"],
        "total_request_ms": first_pass["total_request_ms"],
        "llm_chunks": first_pass["llm_chunks"],
        "llm_chars": first_pass["llm_chars"],
        "meal_card_count": first_pass["meal_card_count"],
        "verdict": _verdict(first_pass),
    }

    if follow_up:
        session_store.save_message(session.session_id, message=ChatMessage(role="user", content=q))
        session_store.save_message(
            session.session_id,
            message=ChatMessage(role="assistant", content="رد سابق مختصر"),
        )
        follow_up_report = await orchestrator.collect_benchmark(session.session_id, follow_up)
        report["follow_up"] = {
            "query": follow_up,
            "route": follow_up_report["route"],
            "rag_used": follow_up_report["rag_used"],
            "history_chars": follow_up_report["history_chars"],
            "prompt_chars": follow_up_report["prompt_chars"],
            "llm_ttft_ms": follow_up_report["llm_ttft_ms"],
            "llm_total_ms": follow_up_report["llm_total_ms"],
            "total_request_ms": follow_up_report["total_request_ms"],
            "verdict": _verdict(follow_up_report),
        }

    return report


def _verdict(report: dict) -> str:
    if report["llm_ttft_ms"] > 5000:
        return (
            "TTFT is dominant. Focus on warmup, smaller prompt prefill, and backend runtime tuning."
        )
    if report["llm_decode_ms"] > report["llm_ttft_ms"] * 2:
        return "Decode is dominant. A smaller routed model or lower output budget should help most."
    if report.get("embed_ms", 0) > 500:
        return "Embedding is unusually slow. Optimize the embedding model or cache/query path."
    return "The hot path looks healthy. If chat still feels slow, inspect network and frontend rendering."

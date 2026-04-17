from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from apps.api.models.chat import (
    ChatRequest,
    SSEDoneEvent,
    SSEMealCardEvent,
    SSETextEvent,
)
from apps.api.services import orchestrator, session_store

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Main chat endpoint — returns an SSE stream.

    SSE event types emitted in order:
      1. "text"       — word-by-word Arabic reply
      2. "meal_cards" — (optional) meal cards to render in the UI
      3. "done"       — signals end of stream
    """
    if session_store.get_session(request.session_id) is None:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

    async def event_generator():
        # Run the full orchestrator (tool loop) — async but non-streaming internally
        llm_response, meal_cards = await orchestrator.run(
            session_id=request.session_id,
            user_message=request.message,
        )

        # Stream reply_ar word-by-word for a natural typing feel
        words = llm_response.reply_ar.split(" ")
        for idx, word in enumerate(words):
            chunk = word if idx == 0 else f" {word}"
            yield {
                "event": "text",
                "data": SSETextEvent(delta=chunk).model_dump_json(),
            }

        # Send meal cards as a single event (if any)
        if meal_cards:
            yield {
                "event": "meal_cards",
                "data": SSEMealCardEvent(cards=meal_cards).model_dump_json(),
            }

        # Signal completion
        yield {
            "event": "done",
            "data": SSEDoneEvent(session_id=request.session_id).model_dump_json(),
        }

    return EventSourceResponse(event_generator())

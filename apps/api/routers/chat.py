from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from apps.api.models.chat import (
    ChatRequest,
    SSEChoicesEvent,
    SSEDoneEvent,
    SSEMealCardEvent,
    SSETextEvent,
)
from apps.api.services import orchestrator, session_store

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Main chat endpoint — true SSE streaming.

    The orchestrator yields events as the LLM produces tokens:
      1. "text"       — each chunk of the Arabic reply as it streams
      2. "meal_cards" — one event with the resolved cards (after ###META###)
      3. "done"       — signals end of stream
    """
    if session_store.get_session(request.session_id) is None:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

    async def event_generator():
        async for ev in orchestrator.run_stream(
            session_id=request.session_id,
            user_message=request.message,
            follow_up_context=request.follow_up_context,
        ):
            kind = ev["event"]
            if kind == "text":
                yield {
                    "event": "text",
                    "data": SSETextEvent(delta=ev["delta"]).model_dump_json(),
                }
            elif kind == "meal_cards":
                yield {
                    "event": "meal_cards",
                    "data": SSEMealCardEvent(cards=ev["cards"]).model_dump_json(),
                }
            elif kind == "choices":
                yield {
                    "event": "choices",
                    "data": SSEChoicesEvent(
                        questions=ev["questions"],
                        submit_label=ev.get("submit_label", "رشّح لي الآن"),
                    ).model_dump_json(),
                }
            elif kind == "done":
                yield {
                    "event": "done",
                    "data": SSEDoneEvent(session_id=ev["session_id"]).model_dump_json(),
                }

    return EventSourceResponse(event_generator())

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.prompts.opening_message_ar import pick_opening, pick_suggestions
from apps.api.models.session import ChatMessage
from apps.api.services import session_store

router = APIRouter(tags=["session"])


class SessionStartRequest(BaseModel):
    table_number: Optional[int] = None


class SessionStateResponse(BaseModel):
    session_id: str
    table_number: Optional[int] = None
    greeting: str
    suggestions: list[str]
    history: list[dict[str, str]]


class SessionMessageAppendRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str


@router.post("/session/start")
async def start_session(request: SessionStartRequest | None = None) -> dict:
    """
    Create a new anonymous session and return:
      - session_id
      - greeting: Arabic opening message ("رسالة افتتاحية")
      - suggestions: 4 quick-action prompt chips
    """
    table_number = request.table_number if request else None
    session = session_store.create_session(table_number=table_number)
    return {
        "session_id": session.session_id,
        "table_number": session.table_number,
        "greeting": pick_opening(),
        "suggestions": pick_suggestions(4),
    }


@router.get("/session/{session_id}", response_model=SessionStateResponse)
async def get_session_state(session_id: str) -> SessionStateResponse:
    session = session_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

    return SessionStateResponse(
        session_id=session.session_id,
        table_number=session.table_number,
        greeting=pick_opening(),
        suggestions=pick_suggestions(4),
        history=[
            {"role": message.role, "content": message.content}
            for message in session.history
            if message.role in {"user", "assistant"} and message.content.strip()
        ],
    )


@router.post("/session/{session_id}/message")
async def append_session_message(
    session_id: str,
    request: SessionMessageAppendRequest,
) -> dict[str, bool]:
    session = session_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="محتوى الرسالة فارغ")

    session_store.save_message(
        session_id,
        ChatMessage(role=request.role, content=content),
    )
    return {"ok": True}

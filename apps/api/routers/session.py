from fastapi import APIRouter

from apps.api.prompts.opening_message_ar import pick_opening, pick_suggestions
from apps.api.services import session_store

router = APIRouter(tags=["session"])


@router.post("/session/start")
async def start_session() -> dict:
    """
    Create a new anonymous session and return:
      - session_id
      - greeting: Arabic opening message ("رسالة افتتاحية")
      - suggestions: 4 quick-action prompt chips
    """
    session = session_store.create_session()
    return {
        "session_id": session.session_id,
        "greeting": pick_opening(),
        "suggestions": pick_suggestions(4),
    }

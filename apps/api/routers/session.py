from fastapi import APIRouter

from apps.api.services import session_store

router = APIRouter(tags=["session"])


@router.post("/session/start")
async def start_session() -> dict:
    """Create a new anonymous session and return its ID."""
    session = session_store.create_session()
    return {"session_id": session.session_id}

from fastapi import APIRouter, HTTPException

from apps.api.services import session_store

router = APIRouter(tags=["cart"])


@router.get("/cart/{session_id}")
async def get_cart(session_id: str) -> dict:
    """Return current cart contents and total for a session."""
    try:
        cart = session_store.get_cart(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    return {
        "session_id": cart.session_id,
        "items": [i.model_dump() for i in cart.items],
        "total": cart.total,
        "currency": "SAR",
    }

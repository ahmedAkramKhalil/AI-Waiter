from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.models.session import CartItem
from apps.api.services import menu_loader, session_store

router = APIRouter(tags=["cart"])


class AddToCartRequest(BaseModel):
    session_id: str
    meal_id: str
    quantity: int = 1


class RemoveFromCartRequest(BaseModel):
    session_id: str
    meal_id: str


def _cart_to_dict(session_id: str) -> dict:
    cart = session_store.get_cart(session_id)
    return {
        "session_id": cart.session_id,
        "items": [i.model_dump() for i in cart.items],
        "total": cart.total,
        "currency": "SAR",
    }


@router.get("/cart/{session_id}")
async def get_cart(session_id: str) -> dict:
    """Return current cart contents and total for a session."""
    try:
        return _cart_to_dict(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")


@router.post("/cart/add")
async def add_to_cart(req: AddToCartRequest) -> dict:
    """Add a meal to the session cart. Returns the updated cart."""
    try:
        session_store.get_cart(req.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

    meal = menu_loader.get_meal_by_id(req.meal_id)
    if meal is None:
        raise HTTPException(status_code=404, detail="الوجبة غير موجودة")

    session_store.add_to_cart(
        req.session_id,
        CartItem(
            meal_id=meal.id,
            name_ar=meal.name_ar,
            quantity=max(1, req.quantity),
            unit_price=meal.price,
            currency=meal.currency,
        ),
    )
    return _cart_to_dict(req.session_id)


@router.post("/cart/remove")
async def remove_from_cart(req: RemoveFromCartRequest) -> dict:
    """Remove a meal from the cart entirely."""
    try:
        cart = session_store.get_cart(req.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

    cart.items = [i for i in cart.items if i.meal_id != req.meal_id]
    return _cart_to_dict(req.session_id)

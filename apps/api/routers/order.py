from fastapi import APIRouter, HTTPException

from apps.api.models.order import OrderConfirmation, OrderRequest
from apps.api.services import session_store

router = APIRouter(tags=["order"])


@router.post("/order/submit")
async def submit_order(request: OrderRequest) -> dict:
    """
    Confirm a mock order from the current cart.
    Clears the cart and returns an order confirmation with a generated order_id.
    """
    try:
        cart = session_store.get_cart(request.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

    if not cart.items:
        raise HTTPException(status_code=400, detail="السلة فارغة — أضف وجبات أولاً")

    confirmation = OrderConfirmation(
        session_id=request.session_id,
        items=list(cart.items),
        total=cart.total,
    )

    session_store.clear_cart(request.session_id)

    return confirmation.model_dump(mode="json")

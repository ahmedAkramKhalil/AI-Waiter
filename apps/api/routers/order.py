from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.models.order import (
    OrderConfirmation,
    OrderRequest,
    WaiterCallNotification,
    WaiterCallRequest,
)
from apps.api.services import session_store

router = APIRouter(tags=["order"])


class AdminOrdersResponse(BaseModel):
    unseen_count: int
    tables: list[dict]
    orders: list[dict]
    waiter_calls: list[dict]


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
        table_number=request.table_number or session_store.get_table_number(request.session_id),
        notes_ar=request.notes_ar,
    )

    session_store.add_order(confirmation)
    session_store.clear_cart(request.session_id)

    return confirmation.model_dump(mode="json")


@router.post("/waiter/call", response_model=WaiterCallNotification)
async def call_waiter(request: WaiterCallRequest) -> WaiterCallNotification:
    if session_store.get_session(request.session_id) is None:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

    call = WaiterCallNotification(
        session_id=request.session_id,
        table_number=request.table_number or session_store.get_table_number(request.session_id),
        note_ar=request.note_ar,
    )
    session_store.add_waiter_call(call)
    return call


@router.get("/admin/orders", response_model=AdminOrdersResponse)
async def get_admin_orders() -> AdminOrdersResponse:
    orders = session_store.list_orders()
    waiter_calls = session_store.list_waiter_calls()
    grouped: dict[int | None, list[OrderConfirmation]] = {}
    for order in orders:
      grouped.setdefault(order.table_number, []).append(order)

    tables = [
        {
            "table_number": table_number,
            "orders_count": len(table_orders),
            "unseen_count": sum(1 for order in table_orders if not order.seen_by_admin),
            "latest_order_id": table_orders[0].order_id if table_orders else None,
            "latest_timestamp": table_orders[0].timestamp if table_orders else None,
            "total_value": round(sum(order.total for order in table_orders), 2),
        }
        for table_number, table_orders in sorted(
            grouped.items(),
            key=lambda item: (
                item[0] is None,
                item[0] if item[0] is not None else 10**9,
            ),
        )
    ]
    return AdminOrdersResponse(
        unseen_count=(
            sum(1 for order in orders if not order.seen_by_admin)
            + sum(1 for call in waiter_calls if not call.seen_by_admin)
        ),
        tables=tables,
        orders=[order.model_dump(mode="json") for order in orders],
        waiter_calls=[call.model_dump(mode="json") for call in waiter_calls],
    )


@router.post("/admin/orders/mark-seen")
async def mark_orders_seen() -> dict:
    session_store.mark_all_orders_seen()
    session_store.mark_all_waiter_calls_seen()
    return {"ok": True}

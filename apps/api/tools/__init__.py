"""Tool dispatcher — maps LLM tool_call names to their implementations."""

from __future__ import annotations

import json

from apps.api.models.session import CartItem
from apps.api.services import menu_loader, rag, session_store


async def dispatch_tool(tool_name: str, arguments: dict, session_id: str) -> str:
    """
    Execute a single tool call and return a JSON string result.
    The result is fed back into the message history for the next LLM call.
    """
    if tool_name == "search_menu":
        query = arguments.get("query", "")
        results = rag.search_menu(query)
        slim = [
            {
                "id": r["id"],
                "name_ar": r["name_ar"],
                "price": r["price"],
                "category": r["category"],
                "spice_level": r["spice_level"],
                "score": r["score"],
            }
            for r in results
        ]
        return json.dumps({"results": slim}, ensure_ascii=False)

    if tool_name == "get_meal_details":
        meal_id = arguments.get("meal_id", "")
        meal = menu_loader.get_meal_by_id(meal_id)
        if meal is None:
            return json.dumps({"error": f"الوجبة {meal_id} غير موجودة"}, ensure_ascii=False)
        return meal.model_dump_json(exclude={"image_url"})

    if tool_name == "add_to_cart":
        meal_id = arguments.get("meal_id", "")
        quantity = int(arguments.get("quantity", 1))
        meal = menu_loader.get_meal_by_id(meal_id)
        if meal is None:
            return json.dumps({"error": f"الوجبة {meal_id} غير موجودة"}, ensure_ascii=False)
        item = CartItem(
            meal_id=meal.id,
            name_ar=meal.name_ar,
            quantity=quantity,
            unit_price=meal.price,
            currency=meal.currency,
        )
        cart = session_store.add_to_cart(session_id, item)
        return json.dumps(
            {
                "success": True,
                "added": meal.name_ar,
                "quantity": quantity,
                "cart_total": cart.total,
                "items_count": len(cart.items),
            },
            ensure_ascii=False,
        )

    if tool_name == "view_cart":
        cart = session_store.get_cart(session_id)
        return json.dumps(
            {
                "items": [
                    {
                        "name_ar": i.name_ar,
                        "quantity": i.quantity,
                        "unit_price": i.unit_price,
                        "subtotal": round(i.unit_price * i.quantity, 2),
                    }
                    for i in cart.items
                ],
                "total": cart.total,
                "currency": "SAR",
            },
            ensure_ascii=False,
        )

    return json.dumps({"error": f"أداة غير معروفة: {tool_name}"}, ensure_ascii=False)

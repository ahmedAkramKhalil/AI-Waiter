"""
Single-pass orchestrator — RAG-first approach.

Flow per request (ONE LLM call only):
  1. RAG search user message → top-5 relevant meals
  2. Build messages: system_prompt + history + rag_context + user message
  3. Single LLM call → LLMResponse JSON
  4. If add_to_cart_confirmation → execute add_to_cart directly
  5. Resolve meal_ids_to_show → MealCard list
  6. Persist messages to session history
  7. Return (LLMResponse, list[MealCard])

Why single-pass: eliminates 2-3 LLM calls per request, cuts latency from ~20s to ~7s.
"""

from __future__ import annotations

import json

from apps.api.models.chat import MealCard
from apps.api.models.llm import LLMResponse
from apps.api.models.session import CartItem, ChatMessage
from apps.api.prompts.system_prompt_ar import SYSTEM_PROMPT
from apps.api.services import llm_client, menu_loader, rag, session_store


async def run(session_id: str, user_message: str) -> tuple[LLMResponse, list[MealCard]]:
    """
    Single-pass RAG orchestrator.
    Returns (LLMResponse, meal_cards_to_display).
    """
    # 1. RAG search — always search, inject results as context
    rag_results = rag.search_menu(user_message, top_k=3)
    rag_context = _format_rag_context(rag_results)

    # 2. Build message list
    history = session_store.get_recent_history(session_id)
    cart = session_store.get_cart(session_id)
    cart_summary = _format_cart(cart)

    system_with_context = (
        f"## القائمة المقترحة:\n{rag_context}"
        f"\n\n## السلة:\n{cart_summary}"
        f"\n\n{SYSTEM_PROMPT}"
    )

    messages: list[dict] = [{"role": "system", "content": system_with_context}]

    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": user_message})

    # 3. Single LLM call
    llm_response = await llm_client.call_llm(messages)

    # 4. Execute cart action if LLM decided to add something
    if llm_response.add_to_cart_confirmation and llm_response.meal_ids_to_show:
        meal_id = llm_response.meal_ids_to_show[0]
        meal = menu_loader.get_meal_by_id(meal_id)
        if meal:
            session_store.add_to_cart(
                session_id,
                CartItem(
                    meal_id=meal.id,
                    name_ar=meal.name_ar,
                    quantity=1,
                    unit_price=meal.price,
                    currency=meal.currency,
                ),
            )

    # 5. Resolve meal cards
    meal_cards: list[MealCard] = []
    for meal_id in llm_response.meal_ids_to_show:
        meal = menu_loader.get_meal_by_id(meal_id)
        if meal:
            meal_cards.append(
                MealCard(
                    meal_id=meal.id,
                    name_ar=meal.name_ar,
                    price=meal.price,
                    currency=meal.currency,
                    image_url=meal.image_url,
                    spice_level=meal.spice_level,
                    calories=meal.calories,
                )
            )

    # 6. Persist history
    session_store.save_message(
        session_id, ChatMessage(role="user", content=user_message)
    )
    session_store.save_message(
        session_id, ChatMessage(role="assistant", content=llm_response.reply_ar)
    )

    return llm_response, meal_cards


def _format_rag_context(results: list[dict]) -> str:
    """Format RAG results as compact Arabic context for the LLM."""
    if not results:
        return "لا توجد نتائج مطابقة."
    lines = []
    for r in results:
        lines.append(
            f"- [{r['id']}] {r['name_ar']} | {r['price']} ريال"
            f" | حرارة: {r['spice_level']}/5"
            f" | {r['category']}"
        )
    return "\n".join(lines)


def _format_cart(cart) -> str:
    """Format cart as compact Arabic summary."""
    if not cart.items:
        return "السلة فارغة."
    lines = [f"- {i.name_ar} × {i.quantity} = {i.unit_price * i.quantity:.0f} ريال"
             for i in cart.items]
    lines.append(f"الإجمالي: {cart.total:.0f} ريال")
    return "\n".join(lines)

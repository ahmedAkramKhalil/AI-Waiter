"""
Streaming single-pass orchestrator — RAG-first, true SSE streaming.

Flow per request:
  1. RAG search user message → top-N relevant meals
  2. Build messages: compact system_prompt + history + rag_context + user message
  3. Stream LLM tokens:
       - Text tokens BEFORE '###META###' → forwarded to client as 'text' SSE events
       - Tokens AFTER '###META###' → accumulated as JSON metadata
  4. Parse meta JSON → resolve meal cards, execute cart add if add_to_cart=true
  5. Emit 'meal_cards' + 'done'
  6. Persist messages to history

Why this is fast: user sees the first Arabic word typically ~0.8-1.5s after sending
(time to first token), not after the whole response is generated.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from apps.api.models.chat import MealCard
from apps.api.models.session import CartItem, ChatMessage
from apps.api.prompts.system_prompt_ar import SYSTEM_PROMPT
from apps.api.services import llm_client, menu_loader, rag, session_store

META_SENTINEL = "###META###"


def _format_rag_context(results: list[dict]) -> str:
    if not results:
        return "لا توجد نتائج."
    return "\n".join(
        f"- [{r['id']}] {r['name_ar']} | {r['price']} ريال"
        f" | حرارة {r['spice_level']}/5 | {r['category']}"
        for r in results
    )


def _format_cart(cart) -> str:
    if not cart.items:
        return "فارغة."
    lines = [
        f"- {i.name_ar} × {i.quantity} = {i.unit_price * i.quantity:.0f} ريال"
        for i in cart.items
    ]
    lines.append(f"الإجمالي: {cart.total:.0f} ريال")
    return "\n".join(lines)


def _build_messages(session_id: str, user_message: str) -> list[dict]:
    rag_results = rag.search_menu(user_message, top_k=3)
    rag_context = _format_rag_context(rag_results)
    history = session_store.get_recent_history(session_id)
    cart = session_store.get_cart(session_id)
    cart_summary = _format_cart(cart)

    system_with_context = (
        f"## القائمة المقترحة:\n{rag_context}\n\n"
        f"## السلة:\n{cart_summary}\n\n"
        f"{SYSTEM_PROMPT}"
    )

    messages: list[dict] = [{"role": "system", "content": system_with_context}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def _resolve_cards(meal_ids: list[str]) -> list[MealCard]:
    cards: list[MealCard] = []
    for mid in meal_ids:
        meal = menu_loader.get_meal_by_id(mid)
        if meal:
            cards.append(
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
    return cards


def _parse_meta(meta_raw: str) -> tuple[list[str], bool]:
    """Extract the first balanced {...} from meta_raw and parse it."""
    s = meta_raw.strip()
    depth = 0
    start = -1
    for i, ch in enumerate(s):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    obj = json.loads(s[start : i + 1])
                    meal_ids = obj.get("meal_ids", []) or obj.get("meal_ids_to_show", [])
                    add_flag = bool(obj.get("add_to_cart", False) or obj.get("add_to_cart_confirmation", False))
                    return meal_ids, add_flag
                except json.JSONDecodeError:
                    start = -1
    return [], False


async def run_stream(
    session_id: str, user_message: str
) -> AsyncIterator[dict]:
    """
    Async generator yielding SSE-ready dicts:
      {"event": "text", "data": {...}}
      {"event": "meal_cards", "data": {...}}
      {"event": "done", "data": {...}}

    Keeps the full reply text to persist at the end.
    """
    messages = _build_messages(session_id, user_message)

    reply_text_parts: list[str] = []
    meta_parts: list[str] = []
    in_meta = False
    carry = ""  # buffer for partial sentinel matches

    async for chunk in llm_client.stream_text(messages):
        if not chunk:
            continue

        if in_meta:
            meta_parts.append(chunk)
            continue

        # We're still in the visible reply portion.
        # Watch for the META sentinel appearing across chunk boundaries.
        combined = carry + chunk
        idx = combined.find(META_SENTINEL)
        if idx != -1:
            # Emit everything before the sentinel, then switch to meta mode.
            visible = combined[:idx]
            if visible:
                reply_text_parts.append(visible)
                yield {"event": "text", "delta": visible}
            meta_parts.append(combined[idx + len(META_SENTINEL) :])
            in_meta = True
            carry = ""
            continue

        # Sentinel may be split across chunks; hold back up to len(sentinel)-1 chars.
        hold = len(META_SENTINEL) - 1
        if len(combined) > hold:
            emit = combined[:-hold]
            carry = combined[-hold:]
            if emit:
                reply_text_parts.append(emit)
                yield {"event": "text", "delta": emit}
        else:
            carry = combined

    # Stream ended. Flush any held-back text (no sentinel was seen).
    if not in_meta and carry:
        reply_text_parts.append(carry)
        yield {"event": "text", "delta": carry}

    # Parse META and resolve actions.
    meta_raw = "".join(meta_parts)
    meal_ids, add_flag = _parse_meta(meta_raw)

    if add_flag and meal_ids:
        meal = menu_loader.get_meal_by_id(meal_ids[0])
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

    cards = _resolve_cards(meal_ids)
    if cards:
        yield {
            "event": "meal_cards",
            "cards": [c.model_dump() for c in cards],
        }

    # Persist history.
    reply_text = "".join(reply_text_parts).strip()
    session_store.save_message(session_id, ChatMessage(role="user", content=user_message))
    session_store.save_message(
        session_id, ChatMessage(role="assistant", content=reply_text or "…")
    )

    yield {"event": "done", "session_id": session_id}

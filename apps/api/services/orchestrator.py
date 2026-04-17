"""
Tool-calling orchestrator.

Flow per request:
  1. Build message list: system_prompt + recent history + new user message
  2. Loop (max MAX_TOOL_ITERATIONS):
       a. Call LLM with guided_json → always returns LLMResponse JSON
       b. If tool_calls is empty → final answer, exit loop
       c. Execute each tool, append (assistant intent + tool result) to messages
  3. Resolve meal_ids_to_show → MealCard list
  4. Persist user + assistant messages to session history
  5. Return (LLMResponse, list[MealCard])
"""

from __future__ import annotations

import json

from apps.api.config import settings
from apps.api.models.chat import MealCard
from apps.api.models.llm import LLMResponse
from apps.api.models.session import ChatMessage
from apps.api.prompts.system_prompt_ar import SYSTEM_PROMPT
from apps.api.services import llm_client, menu_loader, session_store
from apps.api.tools import dispatch_tool


async def run(session_id: str, user_message: str) -> tuple[LLMResponse, list[MealCard]]:
    """
    Run the full tool-calling loop for a single user turn.
    Returns the final LLMResponse and any MealCards to display.
    """
    # 1. Build initial message list
    history = session_store.get_recent_history(session_id)
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    for msg in history:
        entry: dict = {"role": msg.role, "content": msg.content}
        if msg.tool_call_id:
            entry["tool_call_id"] = msg.tool_call_id
        messages.append(entry)

    messages.append({"role": "user", "content": user_message})

    # 2. Tool-calling loop
    llm_response = LLMResponse()
    for iteration in range(1, settings.max_tool_iterations + 1):
        llm_response = await llm_client.call_llm(messages)

        if not llm_response.tool_calls:
            break  # Model has a final answer

        for tc in llm_response.tool_calls:
            call_id = f"call_{tc.name}_{iteration}"

            # Append assistant's tool-call intent
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "tool_calls": [
                                {"name": tc.name, "arguments": tc.arguments}
                            ]
                        },
                        ensure_ascii=False,
                    ),
                }
            )

            # Execute tool
            tool_result = await dispatch_tool(tc.name, tc.arguments, session_id)

            # Append tool result
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": tool_result,
                }
            )

    # 3. Resolve meal cards
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

    # 4. Persist to session history
    session_store.save_message(
        session_id, ChatMessage(role="user", content=user_message)
    )
    session_store.save_message(
        session_id, ChatMessage(role="assistant", content=llm_response.reply_ar)
    )

    return llm_response, meal_cards

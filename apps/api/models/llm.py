from typing import Literal

from pydantic import BaseModel


class ToolCall(BaseModel):
    name: Literal["search_menu", "get_meal_details", "add_to_cart", "view_cart"]
    arguments: dict


class LLMResponse(BaseModel):
    """
    Every LLM call returns exactly this JSON shape (enforced by guided_json).
    Either tool_calls is non-empty (model wants a tool) OR reply_ar is
    non-empty (model has a final answer) — never both simultaneously.
    """

    tool_calls: list[ToolCall] = []
    reply_ar: str = ""
    meal_ids_to_show: list[str] = []
    add_to_cart_confirmation: bool = False

from typing import Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str  # Arabic user text


class MealCard(BaseModel):
    meal_id: str
    name_ar: str
    price: float
    currency: str
    image_url: str
    spice_level: int
    calories: int


class SSETextEvent(BaseModel):
    type: Literal["text"] = "text"
    delta: str


class SSEMealCardEvent(BaseModel):
    type: Literal["meal_cards"] = "meal_cards"
    cards: list[MealCard]


class SSEDoneEvent(BaseModel):
    type: Literal["done"] = "done"
    session_id: str

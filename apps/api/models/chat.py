from typing import Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str  # Arabic user text
    follow_up_context: str | None = None


class MealCard(BaseModel):
    meal_id: str
    name_ar: str
    price: float
    currency: str
    image_url: str
    spice_level: int
    calories: int


class ChoiceOption(BaseModel):
    id: str
    label: str
    value: str


class ChoiceQuestion(BaseModel):
    id: str
    label: str
    options: list[ChoiceOption]


class SSETextEvent(BaseModel):
    type: Literal["text"] = "text"
    delta: str


class SSEMealCardEvent(BaseModel):
    type: Literal["meal_cards"] = "meal_cards"
    cards: list[MealCard]


class SSEChoicesEvent(BaseModel):
    type: Literal["choices"] = "choices"
    questions: list[ChoiceQuestion]
    submit_label: str = "رشّح لي الآن"


class SSEDoneEvent(BaseModel):
    type: Literal["done"] = "done"
    session_id: str

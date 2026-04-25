from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CartItem(BaseModel):
    meal_id: str
    name_ar: str
    quantity: int = 1
    unit_price: float
    currency: str = "SAR"


class Cart(BaseModel):
    session_id: str
    items: list[CartItem] = Field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(i.unit_price * i.quantity for i in self.items), 2)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None


class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    history: list[ChatMessage] = Field(default_factory=list)
    cart: Optional[Cart] = None
    table_number: Optional[int] = None

    def model_post_init(self, __context):  # noqa: ANN001
        if self.cart is None:
            self.cart = Cart(session_id=self.session_id)

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from apps.api.models.session import CartItem


class OrderRequest(BaseModel):
    session_id: str
    table_number: Optional[int] = None
    notes_ar: Optional[str] = None


class OrderConfirmation(BaseModel):
    order_id: str = Field(
        default_factory=lambda: f"ORD-{uuid.uuid4().hex[:8].upper()}"
    )
    session_id: str
    items: list[CartItem]
    total: float
    currency: str = "SAR"
    status: str = "confirmed"
    estimated_minutes: int = 25
    timestamp: datetime.datetime = Field(
        default_factory=datetime.datetime.utcnow
    )

"""
In-memory session store.
Single process only — use --workers 1 with uvicorn.
Natural upgrade path: replace this module's internals with Redis.
"""

from __future__ import annotations

from apps.api.config import settings
from apps.api.models.session import Cart, CartItem, ChatMessage, Session

# Module-level singletons — live for the process lifetime
_sessions: dict[str, Session] = {}


# ── Session management ────────────────────────────────────────────────────────

def create_session() -> Session:
    s = Session()
    _sessions[s.session_id] = s
    return s


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def require_session(session_id: str) -> Session:
    s = _sessions.get(session_id)
    if s is None:
        raise KeyError(f"Session '{session_id}' not found")
    return s


# ── History management ────────────────────────────────────────────────────────

def save_message(session_id: str, message: ChatMessage) -> None:
    session = require_session(session_id)
    session.history.append(message)
    # Trim to keep only the most recent messages
    max_keep = settings.max_history_messages * 2
    if len(session.history) > max_keep:
        session.history = session.history[-max_keep:]


def get_recent_history(session_id: str) -> list[ChatMessage]:
    session = require_session(session_id)
    return session.history[-settings.max_history_messages :]


# ── Cart management ───────────────────────────────────────────────────────────

def add_to_cart(session_id: str, item: CartItem) -> Cart:
    session = require_session(session_id)
    # Merge quantity if the same meal already exists
    for existing in session.cart.items:
        if existing.meal_id == item.meal_id:
            existing.quantity += item.quantity
            return session.cart
    session.cart.items.append(item)
    return session.cart


def get_cart(session_id: str) -> Cart:
    return require_session(session_id).cart


def clear_cart(session_id: str) -> None:
    require_session(session_id).cart.items.clear()

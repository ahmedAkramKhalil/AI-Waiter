"""
Opening greeting + smart suggestion chips for every new session.

Suggestions are generated from the live menu (featured / recommendation_rank /
category / spice / price) with a time-of-day nudge, so the quick-start chips
actually reflect today's recommendations instead of hard-coded strings.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Iterable

from apps.api.models.menu import Meal
from apps.api.services.menu_loader import load_menu

# ── Greetings ────────────────────────────────────────────────────────────────

OPENING_MESSAGES: list[str] = [
    "أهلين فيك بمطعم الأصالة 🌙 أنا أصيل، نادلك اليوم. قلّي شو ذوقك وأنا برشّحلك طبق بيليق فيك.",
    "مرحبا فيك بمطعم الأصالة ✨ عندي اليوم ترشيحات جاهزة. بتحب إشي حار، خفيف، مشبّع، ولا حلو؟",
    "يا هلا وألف مرحبا 🌹 أنا أصيل. إذا بدك ترشيح موفّق من الأول، قلّي ميزانيتك أو ذوقك وأنا بتكفّل بالباقي.",
    "أهلين فيك 🍽️ بمطعم الأصالة. عنا اليوم أطباق مميزة وخيارات بتناسب كل الميزانيات، بتحب أبلّشلك؟",
]


# ── Evergreen (always-useful) prompts ────────────────────────────────────────

# These always make sense regardless of menu/time. We mix 1–2 of these with 2–3
# menu-derived ones so the chips stay fresh without drifting into nonsense.
_EVERGREEN_PROMPTS: list[str] = [
    "أريد شيئًا حارًا وغير مكلف",
    "اقترح لي طبقًا رئيسيًا",
    "أريد شيئًا خفيفًا وصحيًا",
    "ما الأكثر طلبًا لديكم؟",
    "بماذا تنصحني اليوم؟",
]


# ── Time-of-day tuning ───────────────────────────────────────────────────────

def _time_of_day(now: datetime | None = None) -> str:
    """Return 'morning' | 'midday' | 'evening' | 'late'."""
    hour = (now or datetime.now()).hour
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 16:
        return "midday"
    if 16 <= hour < 22:
        return "evening"
    return "late"


def _time_context_prompt(slot: str) -> str | None:
    """A chip that nods to the time of day (optional sprinkle)."""
    return {
        "morning": "أريد فطورًا خفيفًا",
        "midday": "أريد غداءً مشبعًا",
        "evening": "رشّح لي عشاءً لذيذًا",
        "late": "أريد شيئًا حلوًا قبل النوم",
    }.get(slot)


# ── Meal → prompt phrasing ───────────────────────────────────────────────────

def _prompt_from_meal(meal: Meal) -> str:
    """Turn a meal into a natural spoken-Arabic quick-start chip."""
    # Prefer a very short, guest-like question grounded in this specific meal.
    name = meal.name_ar
    if meal.category == "حلويات":
        return f"أريد أن أجرّب {name}"
    if meal.category == "مشروبات":
        return f"بماذا تنصحني مع {name}؟"
    if meal.category in {"مقبلات", "سلطات"}:
        return f"ما رأيك بـ{name}؟"
    # Mains / grills / rice / stews → natural recommendation ask
    return f"أخبرني عن {name}"


# ── Ranking helpers ──────────────────────────────────────────────────────────

def _meal_score(meal: Meal, slot: str) -> float:
    """Blend featured, recommendation_rank, and time-of-day fit into one score."""
    score = 0.0
    if meal.featured:
        score += 3.0
    score += min(meal.recommendation_rank, 5) * 0.8

    # Time-of-day nudge (soft, not strict)
    cat = meal.category or ""
    if slot == "morning" and cat in {"مقبلات", "سلطات", "مشروبات"}:
        score += 1.0
    if slot == "midday" and cat in {"أطباق رئيسية", "مشاوي", "أرز", "كبسة"}:
        score += 1.0
    if slot == "evening" and cat in {"أطباق رئيسية", "مشاوي"}:
        score += 1.2
    if slot == "late" and cat in {"حلويات", "مشروبات"}:
        score += 1.5

    # Spice/calorie/price variety nudges so we don't always pick the same top-2
    if meal.spice_level >= 3:
        score += 0.15
    if meal.calories and meal.calories < 450:
        score += 0.1

    return score


def _pick_diverse(meals: Iterable[Meal], limit: int) -> list[Meal]:
    """Pick top meals but avoid clustering the same category."""
    seen_cats: set[str] = set()
    picked: list[Meal] = []
    for meal in meals:
        if meal.category in seen_cats:
            continue
        picked.append(meal)
        seen_cats.add(meal.category)
        if len(picked) >= limit:
            break
    return picked


# ── Public API ───────────────────────────────────────────────────────────────

def pick_opening() -> str:
    return random.choice(OPENING_MESSAGES)


def pick_suggestions(n: int = 4, *, now: datetime | None = None) -> list[str]:
    """
    Return `n` smart suggestion chips.

    Mix (for n=4):
      • 2 menu-derived chips from top featured / highest-ranked meals
        (distinct categories for visual variety)
      • 1 time-of-day chip ("أبي فطور خفيف" etc.)
      • 1 evergreen fallback ("وش الأكثر طلبًا؟")

    Falls back to pure-evergreen chips if the menu is empty.
    """
    slot = _time_of_day(now)
    suggestions: list[str] = []

    try:
        menu = load_menu()
    except Exception:
        menu = None

    if menu and menu.meals:
        ranked = sorted(menu.meals, key=lambda m: _meal_score(m, slot), reverse=True)
        # Take 2 diverse featured/ranked meals
        menu_picks = _pick_diverse(ranked, limit=2)
        suggestions.extend(_prompt_from_meal(m) for m in menu_picks)

    # Time-of-day chip
    tod = _time_context_prompt(slot)
    if tod and tod not in suggestions:
        suggestions.append(tod)

    # Fill remaining with evergreen, avoiding duplicates
    pool = [p for p in _EVERGREEN_PROMPTS if p not in suggestions]
    random.shuffle(pool)
    while len(suggestions) < n and pool:
        suggestions.append(pool.pop())

    return suggestions[:n]

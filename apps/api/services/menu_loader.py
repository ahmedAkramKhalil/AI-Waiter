import json
from functools import lru_cache
from pathlib import Path

from apps.api.config import settings
from apps.api.models.menu import Meal, Menu


@lru_cache(maxsize=1)
def load_menu() -> Menu:
    path = Path(settings.menu_json_path)
    with open(path, encoding="utf-8") as f:
        raw: list[dict] = json.load(f)
    meals = [Meal(**m) for m in raw]
    categories = sorted({m.category for m in meals})
    return Menu(meals=meals, categories=categories)


def get_meal_by_id(meal_id: str) -> Meal | None:
    menu = load_menu()
    for meal in menu.meals:
        if meal.id == meal_id:
            return meal
    return None

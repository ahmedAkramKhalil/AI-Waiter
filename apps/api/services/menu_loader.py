import json
from functools import lru_cache
from pathlib import Path

from apps.api.config import settings
from apps.api.models.menu import Meal, Menu


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / raw_path


@lru_cache(maxsize=1)
def load_menu() -> Menu:
    path = _resolve_path(settings.menu_json_path)
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


def reload_menu() -> Menu:
    load_menu.cache_clear()
    return load_menu()


def menu_json_path() -> Path:
    return _resolve_path(settings.menu_json_path)


def images_dir_path() -> Path:
    return _resolve_path(settings.images_dir)

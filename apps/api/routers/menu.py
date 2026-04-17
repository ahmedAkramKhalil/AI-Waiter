from fastapi import APIRouter, HTTPException

from apps.api.services.menu_loader import get_meal_by_id, load_menu

router = APIRouter(tags=["menu"])


@router.get("/menu")
async def get_menu() -> dict:
    """Return the full menu with all meals and category list."""
    menu = load_menu()
    return menu.model_dump()


@router.get("/meal/{meal_id}")
async def get_meal(meal_id: str) -> dict:
    """Return details for a single meal including its image URL."""
    meal = get_meal_by_id(meal_id)
    if meal is None:
        raise HTTPException(status_code=404, detail=f"الوجبة '{meal_id}' غير موجودة")
    return meal.model_dump()

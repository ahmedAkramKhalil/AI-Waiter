from fastapi import APIRouter, File, HTTPException, UploadFile

from apps.api.models.menu import ImageUploadResponse, MealUpsert
from apps.api.services import menu_admin
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


@router.post("/admin/menu/meal")
async def upsert_menu_meal(payload: MealUpsert) -> dict:
    meal = menu_admin.upsert_meal(payload)
    return meal.model_dump()


@router.delete("/admin/menu/meal/{meal_id}")
async def delete_menu_meal(meal_id: str) -> dict:
    if get_meal_by_id(meal_id) is None:
        raise HTTPException(status_code=404, detail=f"الوجبة '{meal_id}' غير موجودة")
    menu_admin.delete_meal(meal_id)
    return {"ok": True, "meal_id": meal_id}


@router.post("/admin/menu/upload-image", response_model=ImageUploadResponse)
async def upload_menu_image(file: UploadFile = File(...)) -> ImageUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="اسم الملف مطلوب")
    image_id, image_url = menu_admin.store_image(file.filename, file.file)
    return ImageUploadResponse(image_id=image_id, image_url=image_url)

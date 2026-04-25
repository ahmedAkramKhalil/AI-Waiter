from __future__ import annotations

import json
import shutil
import unicodedata
from pathlib import Path

from qdrant_client.models import Distance, PointStruct, VectorParams

from apps.api.models.menu import Meal, MealUpsert
from apps.api.services import menu_loader, rag


def _clean_filename_stem(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip()
    cleaned = "".join(ch for ch in value if ch not in '\\/:*?"<>|').strip()
    return cleaned or "meal"


def list_meals() -> list[Meal]:
    return menu_loader.load_menu().meals


def save_meals(meals: list[Meal]) -> list[Meal]:
    path = menu_loader.menu_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [meal.model_dump(exclude={"image_url"}) for meal in meals]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    menu_loader.reload_menu()
    refresh_search_index()
    return menu_loader.load_menu().meals


def upsert_meal(payload: MealUpsert) -> Meal:
    meals = list_meals()
    updated = Meal(**payload.model_dump())
    replaced = False
    for idx, meal in enumerate(meals):
        if meal.id == updated.id:
            meals[idx] = updated
            replaced = True
            break
    if not replaced:
        meals.append(updated)
    save_meals(meals)
    return updated


def delete_meal(meal_id: str) -> None:
    meals = [meal for meal in list_meals() if meal.id != meal_id]
    save_meals(meals)


def store_image(filename: str, source_file) -> tuple[str, str]:
    images_dir = menu_loader.images_dir_path()
    images_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower() or ".jpg"
    stem = _clean_filename_stem(Path(filename).stem)
    candidate = f"{stem}{suffix}"
    counter = 1
    while (images_dir / candidate).exists():
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1
    target = images_dir / candidate
    with open(target, "wb") as f:
        shutil.copyfileobj(source_file, f)
    return candidate, f"/images/{candidate}"


def refresh_search_index() -> None:
    menu = menu_loader.load_menu()
    embedder = rag.get_embedder()
    client = rag.get_qdrant()
    texts = [build_searchable_text(meal.model_dump(exclude={"image_url"})) for meal in menu.meals]
    if not texts:
        return
    vectors = embedder.encode(texts, normalize_embeddings=True)
    vector_size = len(vectors[0])
    client.recreate_collection(
        collection_name=rag.settings.qdrant_collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    points = [
        PointStruct(
            id=idx,
            vector=vectors[idx].tolist(),
            payload=menu.meals[idx].model_dump(exclude={"image_url"}),
        )
        for idx in range(len(menu.meals))
    ]
    client.upsert(collection_name=rag.settings.qdrant_collection, points=points)


def build_searchable_text(meal: dict) -> str:
    featured_tokens = " ".join(["مميز", "موصى", "ترشيح"] if meal.get("featured") else [])
    pitch = meal.get("sales_pitch_ar", "")
    rank = " ".join(["أولوية"] * max(int(meal.get("recommendation_rank", 0)), 0))
    return (
        f"{meal['name_ar']} {meal['name_ar']} "
        f"{meal['description_ar']} "
        f"{' '.join(meal['ingredients'])} "
        f"{' '.join(meal['tags'])} "
        f"{meal['category']} "
        f"{featured_tokens} {pitch} {rank}"
    )

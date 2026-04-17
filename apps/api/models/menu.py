from pydantic import BaseModel, computed_field


class Meal(BaseModel):
    id: str
    name_ar: str
    description_ar: str
    ingredients: list[str]
    allergens: list[str]
    tags: list[str]
    category: str
    price: float
    currency: str = "SAR"
    spice_level: int  # 0–5
    calories: int
    image_id: str

    @computed_field
    @property
    def image_url(self) -> str:
        return f"/images/{self.image_id}"


class Menu(BaseModel):
    meals: list[Meal]
    categories: list[str]

from pydantic import BaseModel, Field, computed_field


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
    featured: bool = False
    recommendation_rank: int = 0
    sales_pitch_ar: str = ""

    @computed_field
    @property
    def image_url(self) -> str:
        return f"/images/{self.image_id}"


class Menu(BaseModel):
    meals: list[Meal]
    categories: list[str]


class MealUpsert(BaseModel):
    id: str
    name_ar: str
    description_ar: str
    ingredients: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    category: str
    price: float
    currency: str = "SAR"
    spice_level: int
    calories: int
    image_id: str
    featured: bool = False
    recommendation_rank: int = 0
    sales_pitch_ar: str = ""


class ImageUploadResponse(BaseModel):
    image_id: str
    image_url: str

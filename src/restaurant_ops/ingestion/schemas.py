"""Pydantic schemas for the manually maintained seed tables.

These validate `data/seed/*.csv` on load. They intentionally mirror the
CSV columns one-to-one rather than reshaping the data, so validation
failures point directly at a source column.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Unit = Literal["kilograms", "litres", "each", "portions"]
SourceType = Literal["synthetic", "public_source"]


class MenuItem(BaseModel):
    menu_item_id: str
    item_name: str
    category: str
    selling_price: float = Field(gt=0)
    estimated_prep_minutes: int = Field(gt=0)
    vegetarian: bool
    vegan: bool
    gluten_free: bool
    available_for_delivery: bool
    base_popularity_weight: float = Field(gt=0)
    cold_weather_affinity: float = Field(gt=0)
    hot_weather_affinity: float = Field(gt=0)
    lunch_affinity: float = Field(gt=0)
    dinner_affinity: float = Field(gt=0)
    delivery_affinity: float = Field(gt=0)
    source_type: SourceType
    source_url: str | None = None


class Ingredient(BaseModel):
    ingredient_id: str
    ingredient_name: str
    ingredient_category: str
    unit: Unit
    estimated_unit_cost: float = Field(ge=0)
    shelf_life_days: int = Field(gt=0)
    reorder_level: float = Field(ge=0)
    safety_stock: float = Field(ge=0)
    supplier_id: str
    synthetic_estimate: bool


class Supplier(BaseModel):
    supplier_id: str
    supplier_name: str
    supplier_category: str
    average_lead_time_days: int = Field(ge=0)
    reliability_score: float = Field(ge=0, le=1)
    synthetic_estimate: bool


class Recipe(BaseModel):
    menu_item_id: str
    ingredient_id: str
    quantity_required: float = Field(gt=0)
    unit: Unit
    estimated_wastage_pct: float = Field(ge=0, lt=1)

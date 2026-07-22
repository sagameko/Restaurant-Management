"""Pydantic schemas for the seed tables and the generated operational tables.

Seed schemas (`MenuItem`, `Ingredient`, `Supplier`, `Recipe`) validate
`data/seed/*.csv` on load and mirror the CSV columns one-to-one, so
validation failures point directly at a source column.

Generated schemas (`DailyContext`, `Order`, `OrderItem`, `Review`)
document the shape of the tables produced by `restaurant_ops.generation`.
Bulk validation of the (large) generated datasets uses the vectorised
pandas checks in `restaurant_ops.validation.rules` rather than per-row
Pydantic validation, for performance; these models are the source of
truth for what a valid row looks like and are used directly in tests.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Unit = Literal["kilograms", "litres", "each", "portions"]
SourceType = Literal["synthetic", "public_source"]
Channel = Literal["dine_in", "pickup", "uber_eats", "doordash"]
Daypart = Literal["lunch", "dinner"]
OrderStatus = Literal["Completed", "Cancelled", "Partially Refunded"]
ItemStatus = Literal["Fulfilled", "Missing"]


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


class DailyContext(BaseModel):
    business_date: date
    day_name: str
    temperature_c: float
    rain_mm: float = Field(ge=0)
    weekend_flag: bool
    public_holiday_flag: bool
    city_event_flag: bool
    promotion_name: str | None = None


class Order(BaseModel):
    order_id: str
    order_timestamp: datetime
    business_date: date
    daypart: Daypart
    channel: Channel
    status: OrderStatus
    table_number: int | None = None
    customer_count: int | None = None
    promotion_name: str | None = None
    subtotal: float = Field(ge=0)
    discount_amount: float = Field(ge=0)
    refund_amount: float = Field(ge=0)
    platform_commission: float = Field(ge=0)
    net_sales: float
    estimated_food_cost: float = Field(ge=0)
    estimated_gross_profit: float
    preparation_minutes: float = Field(gt=0)
    promised_minutes: float = Field(gt=0)
    late_flag: bool
    missing_item_flag: bool
    kitchen_staff_count: int = Field(gt=0)
    front_of_house_staff_count: int = Field(gt=0)
    kitchen_load_ratio: float = Field(ge=0)
    temperature_c: float
    rain_mm: float = Field(ge=0)


class OrderItem(BaseModel):
    order_item_id: str
    order_id: str
    menu_item_id: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)
    estimated_unit_food_cost: float = Field(ge=0)
    line_total: float = Field(ge=0)
    estimated_line_food_cost: float = Field(ge=0)
    special_request: str | None = None
    item_status: ItemStatus


class Review(BaseModel):
    review_id: str
    order_id: str
    review_date: date
    channel: Channel
    rating: int = Field(ge=1, le=5)
    review_text: str
    complaint_category: str | None = None
    response_required_flag: bool

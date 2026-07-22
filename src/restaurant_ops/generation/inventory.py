"""Inventory movement generation.

Simulates a per-ingredient stock ledger across the whole simulation
window: completed order items consume stock according to recipe
quantities, suppliers deliver when stock falls below the reorder level
(with an emergency short-lead-time delivery if a stockout is otherwise
unavoidable), stock occasionally expires or is wasted, and rare stock
adjustments correct for stocktake variance.

`recipes.estimated_wastage_pct` (the Phase 2 food-costing assumption)
doubles as the expected *actual* waste rate here — see
`docs/business_rules.md`.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd

from restaurant_ops.ingestion.schemas import Ingredient, Recipe, Supplier

_MOVEMENT_UNIT_COST_DECIMALS = 4


def _daily_ingredient_consumption(
    orders: pd.DataFrame, order_items: pd.DataFrame, recipes: list[Recipe]
) -> pd.DataFrame:
    """Ingredient quantity consumed per business date, from fulfilled items only."""
    fulfilled_items = order_items[order_items["item_status"] == "Fulfilled"].merge(
        orders[["order_id", "business_date", "status"]], on="order_id"
    )
    fulfilled_items = fulfilled_items[fulfilled_items["status"] != "Cancelled"]

    recipe_df = pd.DataFrame(
        [
            {
                "menu_item_id": r.menu_item_id,
                "ingredient_id": r.ingredient_id,
                "quantity_required": r.quantity_required,
                "estimated_wastage_pct": r.estimated_wastage_pct,
            }
            for r in recipes
        ]
    )

    exploded = fulfilled_items.merge(recipe_df, on="menu_item_id")
    exploded["ingredient_quantity"] = exploded["quantity"] * exploded["quantity_required"]

    consumption = exploded.groupby(["business_date", "ingredient_id"], as_index=False).agg(
        ingredient_quantity=("ingredient_quantity", "sum"),
        estimated_wastage_pct=("estimated_wastage_pct", "mean"),
    )
    return consumption


def _average_daily_consumption(consumption: pd.DataFrame) -> dict[str, float]:
    if consumption.empty:
        return {}
    return consumption.groupby("ingredient_id")["ingredient_quantity"].mean().to_dict()


class _IngredientLedger:
    """Tracks one ingredient's running on-hand balance and pending deliveries."""

    def __init__(self, ingredient: Ingredient, initial_quantity: float):
        self.ingredient = ingredient
        self.on_hand = initial_quantity
        self.pending_delivery_date: date | None = None

    def apply(self, quantity_change: float) -> None:
        self.on_hand = max(0.0, self.on_hand + quantity_change)


def generate_inventory_movements(
    daily_context: pd.DataFrame,
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    ingredients: list[Ingredient],
    suppliers: list[Supplier],
    recipes: list[Recipe],
    business_rules: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate the Inventory movements table for the whole simulation window."""
    inventory_cfg = business_rules["inventory"]
    suppliers_by_id = {s.supplier_id: s for s in suppliers}
    consumption = _daily_ingredient_consumption(orders, order_items, recipes)
    average_daily_consumption = _average_daily_consumption(consumption)
    consumption_by_ingredient = {
        ingredient_id: group.set_index("business_date")
        for ingredient_id, group in consumption.groupby("ingredient_id")
    }

    business_dates: list[date] = list(daily_context["business_date"])
    simulation_end = business_dates[-1]

    movement_rows: list[dict] = []
    movement_counter = 0
    delivery_counter = 0
    adjustment_counter = 0
    expiry_counter = 0

    def next_id(prefix: str, counter_name: str) -> str:
        nonlocal delivery_counter, adjustment_counter, expiry_counter
        if counter_name == "delivery":
            delivery_counter += 1
            return f"{prefix}{delivery_counter:06d}"
        if counter_name == "adjustment":
            adjustment_counter += 1
            return f"{prefix}{adjustment_counter:06d}"
        expiry_counter += 1
        return f"{prefix}{expiry_counter:06d}"

    def add_movement(
        business_date: date,
        ingredient: Ingredient,
        movement_type: str,
        quantity_change: float,
        reference_id: str,
        hour: int,
        cost_multiplier: float = 1.0,
    ) -> None:
        nonlocal movement_counter
        movement_counter += 1
        unit_cost = ingredient.estimated_unit_cost * cost_multiplier
        movement_rows.append(
            {
                "movement_id": f"MOV{movement_counter:07d}",
                "movement_timestamp": datetime.combine(business_date, time(hour=hour)),
                "business_date": business_date,
                "ingredient_id": ingredient.ingredient_id,
                "movement_type": movement_type,
                "quantity_change": round(quantity_change, 4),
                "unit": ingredient.unit,
                "unit_cost": round(unit_cost, _MOVEMENT_UNIT_COST_DECIMALS),
                "movement_value": round(quantity_change * unit_cost, 4),
                "reference_id": reference_id,
            }
        )

    for ingredient in ingredients:
        avg_consumption = average_daily_consumption.get(
            ingredient.ingredient_id, ingredient.reorder_level / 7
        )
        initial_quantity = max(
            ingredient.safety_stock,
            avg_consumption * inventory_cfg["initial_stock_days_of_cover"],
        )
        ledger = _IngredientLedger(ingredient, initial_quantity)
        add_movement(
            business_dates[0],
            ingredient,
            "Stock Adjustment",
            initial_quantity,
            "INIT-STOCKTAKE",
            hour=0,
        )

        supplier = suppliers_by_id[ingredient.supplier_id]
        ingredient_consumption = consumption_by_ingredient.get(ingredient.ingredient_id)

        for business_date in business_dates:
            # Arrivals scheduled from a previous day's reorder.
            if ledger.pending_delivery_date == business_date:
                target_quantity = max(
                    ingredient.reorder_level * 2,
                    avg_consumption * inventory_cfg["reorder_target_days_of_cover"],
                )
                delivery_quantity = max(0.0, target_quantity - ledger.on_hand)
                ledger.apply(delivery_quantity)
                add_movement(
                    business_date,
                    ingredient,
                    "Supplier Delivery",
                    delivery_quantity,
                    next_id("DEL", "delivery"),
                    hour=7,
                )
                ledger.pending_delivery_date = None

            # Sales consumption. If today's consumption alone would exceed
            # on-hand stock, trigger a same-day emergency delivery first —
            # this is the spec's "emergency purchasing" driver, and it's
            # what keeps the recorded ledger from ever implying negative
            # stock (a kitchen can't serve ingredient it doesn't have).
            day_quantity = 0.0
            wastage_pct = 0.0
            if ingredient_consumption is not None and business_date in ingredient_consumption.index:
                row = ingredient_consumption.loc[business_date]
                day_quantity = float(row["ingredient_quantity"])
                wastage_pct = float(row["estimated_wastage_pct"])

                if day_quantity > ledger.on_hand:
                    target_quantity = max(
                        ingredient.reorder_level * 2,
                        avg_consumption * inventory_cfg["reorder_target_days_of_cover"],
                        day_quantity,
                    )
                    emergency_quantity = target_quantity - ledger.on_hand
                    ledger.apply(emergency_quantity)
                    add_movement(
                        business_date,
                        ingredient,
                        "Supplier Delivery",
                        emergency_quantity,
                        next_id("DEL", "delivery") + "-EMERGENCY",
                        hour=6,
                        cost_multiplier=inventory_cfg["emergency_cost_multiplier"],
                    )
                    ledger.pending_delivery_date = None

                ledger.apply(-day_quantity)
                add_movement(
                    business_date,
                    ingredient,
                    "Sales Consumption",
                    -day_quantity,
                    business_date.isoformat(),
                    hour=20,
                )

                if (
                    day_quantity > 0
                    and rng.random() < inventory_cfg["waste_probability_per_consumption_day"]
                ):
                    waste_fraction = rng.uniform(
                        *inventory_cfg["waste_fraction_of_daily_consumption_range"]
                    )
                    waste_quantity = min(
                        ledger.on_hand, day_quantity * max(waste_fraction, wastage_pct)
                    )
                    if waste_quantity > 0:
                        ledger.apply(-waste_quantity)
                        add_movement(
                            business_date,
                            ingredient,
                            "Waste",
                            -waste_quantity,
                            business_date.isoformat(),
                            hour=21,
                        )

            # Expiry: short-shelf-life ingredients expire more often.
            expiry_probability = inventory_cfg["expiry_base_probability_per_day"] * (
                inventory_cfg["expiry_reference_shelf_life_days"] / ingredient.shelf_life_days
            )
            if ledger.on_hand > 0 and rng.random() < min(expiry_probability, 0.5):
                expiry_fraction = rng.uniform(*inventory_cfg["expiry_fraction_of_on_hand_range"])
                expiry_quantity = ledger.on_hand * expiry_fraction
                ledger.apply(-expiry_quantity)
                add_movement(
                    business_date,
                    ingredient,
                    "Expired Stock",
                    -expiry_quantity,
                    next_id("EXP", "expiry"),
                    hour=22,
                )

            # Rare stocktake adjustment.
            if rng.random() < inventory_cfg["stock_adjustment_probability_per_week"] / 7:
                adjustment_fraction = rng.uniform(*inventory_cfg["stock_adjustment_fraction_range"])
                adjustment_quantity = ledger.on_hand * adjustment_fraction
                ledger.apply(adjustment_quantity)
                add_movement(
                    business_date,
                    ingredient,
                    "Stock Adjustment",
                    adjustment_quantity,
                    next_id("ADJ", "adjustment"),
                    hour=23,
                )

            # Reorder logic: once stock drops below the reorder level,
            # schedule a normal-lead-time delivery for later — this is the
            # proactive path. The reactive path (a same-day emergency
            # delivery when today's consumption would otherwise exceed
            # on-hand stock) is handled above, before consumption is applied.
            if ledger.on_hand < ingredient.reorder_level and ledger.pending_delivery_date is None:
                arrival = business_date + timedelta(days=max(1, supplier.average_lead_time_days))
                if arrival <= simulation_end:
                    ledger.pending_delivery_date = arrival

    return pd.DataFrame(movement_rows)


def compute_closing_inventory(movements: pd.DataFrame) -> pd.DataFrame:
    """Final on-hand quantity/value per ingredient, from the movement ledger."""
    return (
        movements.groupby("ingredient_id", as_index=False)
        .agg(closing_quantity=("quantity_change", "sum"), closing_value=("movement_value", "sum"))
        .round(4)
    )

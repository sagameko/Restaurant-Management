"""Tests for inventory movement generation: reproducibility, the required
inventory relationships (spec section 12), and ledger consistency."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from pandas.testing import assert_frame_equal

from restaurant_ops.config import get_business_rules, get_simulation_settings
from restaurant_ops.generation.inventory import (
    compute_closing_inventory,
    generate_inventory_movements,
)
from restaurant_ops.generation.orders import generate_orders_and_items
from restaurant_ops.generation.staffing import generate_shifts
from restaurant_ops.generation.weather import generate_daily_context
from restaurant_ops.ingestion.loader import (
    load_employees,
    load_ingredients,
    load_menu_items,
    load_recipes,
    load_suppliers,
)
from restaurant_ops.validation.rules import validate_inventory_movements

_START_DATE = date(2025, 7, 1)
_DAYS = 60
_AVERAGE_ORDERS = 60
_SEED = 42


def _generate(seed: int = _SEED):
    business_rules = get_business_rules()
    simulation_settings = get_simulation_settings()
    menu_items = load_menu_items()
    ingredients = load_ingredients()
    suppliers = load_suppliers()
    recipes = load_recipes()
    employees = load_employees()
    rng = np.random.default_rng(seed)

    daily_context = generate_daily_context(_START_DATE, _DAYS, business_rules, rng)
    _shifts, staffing_lookup = generate_shifts(daily_context, employees, business_rules, rng)
    orders, order_items = generate_orders_and_items(
        daily_context,
        menu_items,
        ingredients,
        recipes,
        simulation_settings,
        business_rules,
        rng,
        staffing_lookup,
        average_daily_orders=_AVERAGE_ORDERS,
    )
    movements = generate_inventory_movements(
        daily_context, orders, order_items, ingredients, suppliers, recipes, business_rules, rng
    )
    return movements, orders, order_items


@pytest.fixture(scope="module")
def generated():
    return _generate()


@pytest.fixture(scope="module")
def ingredient_ids():
    return {i.ingredient_id for i in load_ingredients()}


def test_same_seed_produces_identical_movements():
    movements_a, _, _ = _generate(seed=7)
    movements_b, _, _ = _generate(seed=7)
    assert_frame_equal(movements_a, movements_b)


def test_no_validation_errors(generated, ingredient_ids):
    movements, _, _ = generated
    assert validate_inventory_movements(movements, ingredient_ids) == []


def test_running_balance_never_negative(generated):
    movements, _, _ = generated
    sorted_movements = movements.sort_values(["ingredient_id", "movement_timestamp"])
    running_balance = sorted_movements.groupby("ingredient_id")["quantity_change"].cumsum()
    assert (running_balance >= -0.01).all()


def test_every_ingredient_has_movements(generated, ingredient_ids):
    movements, _, _ = generated
    assert set(movements["ingredient_id"]) == ingredient_ids


def test_all_five_movement_types_occur(generated):
    movements, _, _ = generated
    expected_types = {
        "Supplier Delivery",
        "Sales Consumption",
        "Waste",
        "Stock Adjustment",
        "Expired Stock",
    }
    assert expected_types.issubset(set(movements["movement_type"]))


def test_supplier_deliveries_are_never_negative(generated):
    movements, _, _ = generated
    deliveries = movements[movements["movement_type"] == "Supplier Delivery"]
    assert (deliveries["quantity_change"] > 0).all()


def test_consumption_and_waste_and_expiry_are_never_positive(generated):
    movements, _, _ = generated
    for movement_type in ("Sales Consumption", "Waste", "Expired Stock"):
        rows = movements[movements["movement_type"] == movement_type]
        assert (rows["quantity_change"] < 0).all()


def test_consumption_matches_recipe_usage_for_one_ingredient(generated):
    """Total 'Sales Consumption' for an ingredient should equal
    quantity_required (per recipe) x quantity sold, summed over every
    fulfilled, non-cancelled order item for menu items using it — not
    just plausible-looking, but arithmetically exact."""
    movements, orders, order_items = generated
    recipes = load_recipes()

    # ING014 (jasmine_rice) appears in several rice-bowl/side recipes.
    target_ingredient_id = "ING014"
    recipe_lines = [r for r in recipes if r.ingredient_id == target_ingredient_id]
    quantity_required_by_menu_item = {r.menu_item_id: r.quantity_required for r in recipe_lines}

    eligible_items = order_items[order_items["item_status"] == "Fulfilled"].merge(
        orders[["order_id", "status"]], on="order_id"
    )
    eligible_items = eligible_items[eligible_items["status"] != "Cancelled"]
    eligible_items = eligible_items[
        eligible_items["menu_item_id"].isin(quantity_required_by_menu_item)
    ]

    expected_consumption = sum(
        row.quantity * quantity_required_by_menu_item[row.menu_item_id]
        for row in eligible_items.itertuples()
    )

    actual_consumption = -movements.loc[
        (movements["ingredient_id"] == target_ingredient_id)
        & (movements["movement_type"] == "Sales Consumption"),
        "quantity_change",
    ].sum()

    assert actual_consumption == pytest.approx(expected_consumption, rel=1e-3)


def test_closing_inventory_is_non_negative(generated):
    movements, _, _ = generated
    closing = compute_closing_inventory(movements)
    assert (closing["closing_quantity"] >= -0.01).all()

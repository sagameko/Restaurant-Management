"""Tests for order/order-item generation: reproducibility, referential
integrity, financial reconciliation, and the required demand/staffing
relationships (spec section 12)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from restaurant_ops.config import get_business_rules, get_simulation_settings
from restaurant_ops.generation.orders import generate_orders_and_items
from restaurant_ops.generation.weather import generate_daily_context
from restaurant_ops.ingestion.loader import load_ingredients, load_menu_items, load_recipes
from restaurant_ops.validation.rules import validate_order_items, validate_orders

_START_DATE = date(2025, 7, 1)
_DAYS = 60
_AVERAGE_ORDERS = 60
_SEED = 42


def _generate(seed: int = _SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    business_rules = get_business_rules()
    simulation_settings = get_simulation_settings()
    menu_items = load_menu_items()
    ingredients = load_ingredients()
    recipes = load_recipes()
    rng = np.random.default_rng(seed)
    daily_context = generate_daily_context(_START_DATE, _DAYS, business_rules, rng)
    return generate_orders_and_items(
        daily_context,
        menu_items,
        ingredients,
        recipes,
        simulation_settings,
        business_rules,
        rng,
        average_daily_orders=_AVERAGE_ORDERS,
    )


@pytest.fixture(scope="module")
def generated():
    orders, order_items = _generate()
    return orders, order_items


@pytest.fixture(scope="module")
def menu_item_ids():
    return {item.menu_item_id for item in load_menu_items()}


def test_same_seed_produces_identical_orders():
    orders_a, items_a = _generate(seed=7)
    orders_b, items_b = _generate(seed=7)
    assert_frame_equal(orders_a, orders_b)
    assert_frame_equal(items_a, items_b)


def test_different_seed_produces_different_orders():
    orders_a, _ = _generate(seed=7)
    orders_b, _ = _generate(seed=8)
    assert len(orders_a) != len(orders_b) or not orders_a["subtotal"].equals(orders_b["subtotal"])


def test_no_validation_errors(generated, menu_item_ids):
    orders, order_items = generated
    order_errors = validate_orders(orders)
    item_errors = validate_order_items(order_items, set(orders["order_id"]), menu_item_ids)
    assert order_errors == []
    assert item_errors == []


def test_order_items_reference_real_orders_and_menu_items(generated, menu_item_ids):
    orders, order_items = generated
    assert set(order_items["order_id"]).issubset(set(orders["order_id"]))
    assert set(order_items["menu_item_id"]).issubset(menu_item_ids)


def test_every_order_has_at_least_one_item(generated):
    orders, order_items = generated
    orders_with_items = set(order_items["order_id"])
    assert set(orders["order_id"]).issubset(orders_with_items)


def test_financial_reconciliation(generated):
    orders, _ = generated
    expected_net_sales = (
        orders["subtotal"]
        - orders["discount_amount"]
        - orders["refund_amount"]
        - orders["platform_commission"]
    )
    assert (orders["net_sales"] - expected_net_sales).abs().lt(0.02).all()


def test_only_dine_in_orders_have_table_numbers(generated):
    orders, _ = generated
    dine_in = orders["channel"] == "dine_in"
    assert orders.loc[dine_in, "table_number"].notna().all()
    assert orders.loc[~dine_in, "table_number"].isna().all()


def test_delivery_channels_incur_commission_dine_in_and_pickup_do_not(generated):
    orders, _ = generated
    non_cancelled = orders["status"] != "Cancelled"
    delivery = orders["channel"].isin(["uber_eats", "doordash"]) & non_cancelled
    non_delivery = orders["channel"].isin(["dine_in", "pickup"])
    assert (orders.loc[delivery, "platform_commission"] > 0).mean() > 0.9
    assert (orders.loc[non_delivery, "platform_commission"] == 0).all()


def test_delivery_channels_are_later_than_dine_in(generated):
    orders, _ = generated
    late_rate_by_channel = orders.groupby("channel")["late_flag"].mean()
    assert late_rate_by_channel["uber_eats"] > late_rate_by_channel["dine_in"]
    assert late_rate_by_channel["doordash"] > late_rate_by_channel["dine_in"]


def test_lunch_generates_more_pickup_than_dinner(generated):
    orders, _ = generated
    pickup_share_by_daypart = orders.groupby("daypart")["channel"].apply(
        lambda s: (s == "pickup").mean()
    )
    assert pickup_share_by_daypart["lunch"] > pickup_share_by_daypart["dinner"]


def test_friday_and_saturday_dinner_have_higher_volume_than_midweek(generated):
    orders, _ = generated
    dinner = orders[orders["daypart"] == "dinner"].copy()
    dinner["weekday"] = pd.to_datetime(dinner["business_date"]).dt.day_name()
    counts_by_weekday = dinner.groupby("weekday").size()
    midweek_average = counts_by_weekday[["Tuesday", "Wednesday"]].mean()
    assert counts_by_weekday["Friday"] > midweek_average
    assert counts_by_weekday["Saturday"] > midweek_average


def test_higher_kitchen_load_increases_preparation_time(generated):
    orders, _ = generated
    low_load = orders[orders["kitchen_load_ratio"] < 0.6]["preparation_minutes"]
    high_load = orders[orders["kitchen_load_ratio"] > 1.2]["preparation_minutes"]
    assert high_load.mean() > low_load.mean()


def test_higher_kitchen_load_increases_missing_item_and_refund_rates(generated):
    orders, _ = generated
    low_load = orders[orders["kitchen_load_ratio"] < 0.6]
    high_load = orders[orders["kitchen_load_ratio"] > 1.2]
    assert high_load["missing_item_flag"].mean() > low_load["missing_item_flag"].mean()

    refunded_statuses = {"Partially Refunded", "Cancelled"}
    low_refund_rate = low_load["status"].isin(refunded_statuses).mean()
    high_refund_rate = high_load["status"].isin(refunded_statuses).mean()
    assert high_refund_rate > low_refund_rate

"""Tests for review generation: rating formula, range, and the required
operational-outcome relationships (spec section 12)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from restaurant_ops.config import get_business_rules, get_simulation_settings
from restaurant_ops.generation.orders import generate_orders_and_items
from restaurant_ops.generation.reviews import generate_reviews
from restaurant_ops.generation.staffing import generate_shifts
from restaurant_ops.generation.weather import generate_daily_context
from restaurant_ops.ingestion.loader import (
    load_employees,
    load_ingredients,
    load_menu_items,
    load_recipes,
)
from restaurant_ops.validation.rules import validate_reviews

_START_DATE = date(2025, 7, 1)
_DAYS = 60
_AVERAGE_ORDERS = 60
_SEED = 42
_END_DATE = date(2025, 8, 29)


@pytest.fixture(scope="module")
def generated():
    business_rules = get_business_rules()
    simulation_settings = get_simulation_settings()
    menu_items = load_menu_items()
    ingredients = load_ingredients()
    recipes = load_recipes()
    employees = load_employees()
    rng = np.random.default_rng(_SEED)
    daily_context = generate_daily_context(_START_DATE, _DAYS, business_rules, rng)
    _shifts, staffing_lookup = generate_shifts(daily_context, employees, business_rules, rng)
    orders, _ = generate_orders_and_items(
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
    reviews = generate_reviews(orders, _END_DATE, business_rules, rng)
    return orders, reviews


def test_no_validation_errors(generated):
    orders, reviews = generated
    assert validate_reviews(reviews, set(orders["order_id"])) == []


def test_ratings_within_range(generated):
    _, reviews = generated
    assert reviews["rating"].between(1, 5).all()


def test_ratings_are_not_uniform_random(generated):
    """A `random.randint(1, 5)` rating distribution would be roughly flat;
    the operational-outcome formula should skew heavily toward 4-5."""
    _, reviews = generated
    high_rating_share = reviews["rating"].isin([4, 5]).mean()
    assert high_rating_share > 0.6


def test_cancelled_orders_are_never_reviewed(generated):
    orders, reviews = generated
    cancelled_order_ids = set(orders.loc[orders["status"] == "Cancelled", "order_id"])
    assert not (set(reviews["order_id"]) & cancelled_order_ids)


def test_late_orders_receive_lower_ratings(generated):
    orders, reviews = generated
    merged = reviews.merge(orders[["order_id", "late_flag", "missing_item_flag"]], on="order_id")
    on_time = merged[~merged["late_flag"] & ~merged["missing_item_flag"]]["rating"]
    late = merged[merged["late_flag"] & ~merged["missing_item_flag"]]["rating"]
    assert late.mean() < on_time.mean()


def test_missing_item_orders_receive_lower_ratings(generated):
    orders, reviews = generated
    merged = reviews.merge(orders[["order_id", "late_flag", "missing_item_flag"]], on="order_id")
    fulfilled = merged[~merged["late_flag"] & ~merged["missing_item_flag"]]["rating"]
    missing = merged[merged["missing_item_flag"]]["rating"]
    assert missing.mean() < fulfilled.mean()


def test_missing_item_orders_are_flagged_with_that_complaint_category(generated):
    orders, reviews = generated
    merged = reviews.merge(orders[["order_id", "missing_item_flag"]], on="order_id")
    missing_reviews = merged[merged["missing_item_flag"]]
    assert (missing_reviews["complaint_category"] == "Missing Item").all()


def test_low_ratings_require_a_response(generated):
    _, reviews = generated
    low_ratings = reviews[reviews["rating"] <= 2]
    assert low_ratings["response_required_flag"].all()

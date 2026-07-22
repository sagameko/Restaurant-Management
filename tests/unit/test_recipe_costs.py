"""Tests for the Phase 1/2 vertical slice: seed loading, FK validation,
and estimated food-cost calculation."""

from __future__ import annotations

import pytest

from restaurant_ops.ingestion.loader import (
    build_menu_summary,
    build_seed_report,
    compute_menu_item_food_costs,
    load_ingredients,
    load_menu_items,
    load_recipes,
    load_suppliers,
    validate_referential_integrity,
)


@pytest.fixture(scope="module")
def menu_items():
    return load_menu_items()


@pytest.fixture(scope="module")
def ingredients():
    return load_ingredients()


@pytest.fixture(scope="module")
def suppliers():
    return load_suppliers()


@pytest.fixture(scope="module")
def recipes():
    return load_recipes()


def test_seed_files_load_and_validate(menu_items, ingredients, suppliers, recipes):
    assert 45 <= len(menu_items) <= 65
    assert 40 <= len(ingredients) <= 70
    assert len(suppliers) > 0
    assert len(recipes) > 0


def test_menu_item_categories_within_expected_range(menu_items):
    categories = {item.category for item in menu_items}
    assert 8 <= len(categories) <= 12


def test_referential_integrity_passes(menu_items, ingredients, suppliers, recipes):
    # Should not raise: every recipe row points at a real menu item and
    # ingredient, every ingredient points at a real supplier, and every
    # menu item has at least one recipe row.
    validate_referential_integrity(menu_items, ingredients, suppliers, recipes)


def test_referential_integrity_detects_unknown_menu_item(ingredients, suppliers, recipes):
    from restaurant_ops.ingestion.schemas import MenuItem

    broken_menu_items = [
        MenuItem(
            menu_item_id="MI999",
            item_name="Test Item",
            category="Starters",
            selling_price=10.0,
            estimated_prep_minutes=5,
            vegetarian=True,
            vegan=True,
            gluten_free=True,
            available_for_delivery=True,
            base_popularity_weight=1.0,
            cold_weather_affinity=1.0,
            hot_weather_affinity=1.0,
            lunch_affinity=1.0,
            dinner_affinity=1.0,
            delivery_affinity=1.0,
            source_type="synthetic",
        )
    ]
    with pytest.raises(ValueError, match="referential-integrity check failed"):
        validate_referential_integrity(broken_menu_items, ingredients, suppliers, recipes)


def test_estimated_food_cost_matches_manual_calculation(ingredients, recipes):
    # MI041 Steamed Jasmine Rice has a single recipe line: 0.20kg jasmine
    # rice at $2.40/kg with 2% wastage.
    food_costs = compute_menu_item_food_costs(ingredients, recipes)
    rice_row = food_costs.loc[food_costs["menu_item_id"] == "MI041"].iloc[0]
    expected = 0.20 * 2.40 * 1.02
    assert rice_row["estimated_item_food_cost"] == pytest.approx(expected, rel=1e-6)


def test_menu_summary_has_positive_margins_on_average(menu_items, ingredients, recipes):
    summary = build_menu_summary(menu_items, ingredients, recipes)
    assert len(summary) == len(menu_items)
    assert summary["estimated_item_food_cost"].gt(0).all()
    assert summary["estimated_gross_margin_pct"].mean() > 0


def test_seed_report_food_cost_percentage_is_plausible(menu_items, ingredients, recipes):
    report = build_seed_report(menu_items, ingredients, recipes)
    assert report["number_of_menu_items"] == len(menu_items)
    assert report["recipe_coverage_pct"] == 1.0
    assert 0.05 < report["average_estimated_food_cost_pct"] < 0.60

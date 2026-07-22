"""Load, validate and cost the manually maintained seed tables.

This is the first working vertical slice of the platform: read
`menu_items.csv`, `ingredients.csv`, `suppliers.csv` and `recipes.csv`,
confirm every recipe references a real menu item and ingredient, and
calculate each menu item's estimated food cost from its recipe.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from restaurant_ops.config import SEED_DIR
from restaurant_ops.ingestion.schemas import Ingredient, MenuItem, Recipe, Supplier


def _read_seed_csv(path: Path) -> list[dict]:
    # dtype=str now produces pandas' StringDtype (pandas >= 3.0), which
    # silently drops a `None` fill value passed to `.where`. Cast to
    # plain `object` first so empty cells become real `None`, not NaN,
    # which the Pydantic schemas below require for optional fields.
    df = pd.read_csv(path, dtype=str, keep_default_na=True).astype(object)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")


def load_menu_items(path: Path | None = None) -> list[MenuItem]:
    rows = _read_seed_csv(path or SEED_DIR / "menu_items.csv")
    return [MenuItem.model_validate(row) for row in rows]


def load_ingredients(path: Path | None = None) -> list[Ingredient]:
    rows = _read_seed_csv(path or SEED_DIR / "ingredients.csv")
    return [Ingredient.model_validate(row) for row in rows]


def load_suppliers(path: Path | None = None) -> list[Supplier]:
    rows = _read_seed_csv(path or SEED_DIR / "suppliers.csv")
    return [Supplier.model_validate(row) for row in rows]


def load_recipes(path: Path | None = None) -> list[Recipe]:
    rows = _read_seed_csv(path or SEED_DIR / "recipes.csv")
    return [Recipe.model_validate(row) for row in rows]


def validate_referential_integrity(
    menu_items: list[MenuItem],
    ingredients: list[Ingredient],
    suppliers: list[Supplier],
    recipes: list[Recipe],
) -> None:
    """Raise ValueError listing every broken foreign-key reference found."""
    menu_item_ids = {item.menu_item_id for item in menu_items}
    ingredient_ids = {ing.ingredient_id for ing in ingredients}
    supplier_ids = {sup.supplier_id for sup in suppliers}

    errors: list[str] = []

    for ingredient in ingredients:
        if ingredient.supplier_id not in supplier_ids:
            errors.append(
                f"ingredients.csv: {ingredient.ingredient_id} references "
                f"unknown supplier_id {ingredient.supplier_id!r}"
            )

    referenced_menu_items: set[str] = set()
    for recipe in recipes:
        if recipe.menu_item_id not in menu_item_ids:
            errors.append(f"recipes.csv: unknown menu_item_id {recipe.menu_item_id!r}")
        if recipe.ingredient_id not in ingredient_ids:
            errors.append(
                f"recipes.csv: unknown ingredient_id {recipe.ingredient_id!r} "
                f"for menu item {recipe.menu_item_id!r}"
            )
        referenced_menu_items.add(recipe.menu_item_id)

    missing_recipes = menu_item_ids - referenced_menu_items
    for menu_item_id in sorted(missing_recipes):
        errors.append(f"menu_items.csv: {menu_item_id} has no recipe rows")

    if errors:
        raise ValueError("Seed data referential-integrity check failed:\n" + "\n".join(errors))


def compute_menu_item_food_costs(
    ingredients: list[Ingredient], recipes: list[Recipe]
) -> pd.DataFrame:
    """estimated_item_food_cost = sum(quantity_required * unit_cost * (1 + wastage_pct))."""
    unit_cost_by_ingredient = {ing.ingredient_id: ing.estimated_unit_cost for ing in ingredients}

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
    recipe_df["estimated_unit_cost"] = recipe_df["ingredient_id"].map(unit_cost_by_ingredient)
    recipe_df["line_cost"] = (
        recipe_df["quantity_required"]
        * recipe_df["estimated_unit_cost"]
        * (1 + recipe_df["estimated_wastage_pct"])
    )

    return (
        recipe_df.groupby("menu_item_id", as_index=False)["line_cost"]
        .sum()
        .rename(columns={"line_cost": "estimated_item_food_cost"})
    )


def build_menu_summary(
    menu_items: list[MenuItem], ingredients: list[Ingredient], recipes: list[Recipe]
) -> pd.DataFrame:
    """Per-item selling price, estimated food cost, and estimated margin."""
    menu_df = pd.DataFrame(
        [
            {
                "menu_item_id": item.menu_item_id,
                "item_name": item.item_name,
                "category": item.category,
                "selling_price": item.selling_price,
            }
            for item in menu_items
        ]
    )
    food_cost_df = compute_menu_item_food_costs(ingredients, recipes)

    summary = menu_df.merge(food_cost_df, on="menu_item_id", how="left")
    summary["estimated_gross_profit"] = (
        summary["selling_price"] - summary["estimated_item_food_cost"]
    )
    summary["estimated_gross_margin_pct"] = (
        summary["estimated_gross_profit"] / summary["selling_price"]
    )
    return summary.sort_values("menu_item_id").reset_index(drop=True)


def build_seed_report(
    menu_items: list[MenuItem], ingredients: list[Ingredient], recipes: list[Recipe]
) -> dict:
    """Summary counts used by `restaurant-ops validate` and Phase 2 sign-off."""
    summary = build_menu_summary(menu_items, ingredients, recipes)
    menu_item_ids_with_recipes = {r.menu_item_id for r in recipes}

    return {
        "number_of_menu_items": len(menu_items),
        "number_of_categories": len({item.category for item in menu_items}),
        "number_of_ingredients": len(ingredients),
        "recipe_coverage_pct": len(menu_item_ids_with_recipes) / len(menu_items),
        "average_estimated_food_cost_pct": float(
            (summary["estimated_item_food_cost"] / summary["selling_price"]).mean()
        ),
    }

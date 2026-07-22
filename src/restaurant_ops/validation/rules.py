"""Explicit, vectorised validation for generated tables.

The seed layer is small enough to validate row-by-row with Pydantic
(`restaurant_ops.ingestion.schemas` + `loader.py`). The generated tables
are two to three orders of magnitude larger, so these checks use pandas
boolean masks instead — the "explicit validation functions" alternative
the project spec allows alongside Pydantic.

Every `validate_*` function returns a list of human-readable error
strings (empty if the table is clean) rather than raising, so a caller
can run every check and report everything that's wrong at once.
"""

from __future__ import annotations

import pandas as pd

_VALID_CHANNELS = {"dine_in", "pickup", "uber_eats", "doordash"}
_VALID_STATUSES = {"Completed", "Cancelled", "Partially Refunded"}
_VALID_ITEM_STATUSES = {"Fulfilled", "Missing"}
_VALID_DAYPARTS = {"lunch", "dinner"}
_VALID_MOVEMENT_TYPES = {
    "Supplier Delivery",
    "Sales Consumption",
    "Waste",
    "Stock Adjustment",
    "Expired Stock",
}


def _describe_violations(mask: pd.Series, id_column: pd.Series, message: str) -> list[str]:
    count = int(mask.sum())
    if count == 0:
        return []
    examples = id_column[mask].head(5).tolist()
    return [f"{message}: {count} rows (examples: {examples})"]


def validate_daily_context(daily_context: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    errors += _describe_violations(
        daily_context["rain_mm"] < 0, daily_context["business_date"], "Negative rain_mm"
    )
    errors += _describe_violations(
        daily_context["business_date"].isna(),
        daily_context.index.to_series(),
        "Missing business_date",
    )
    return errors


def validate_orders(orders: pd.DataFrame, monetary_tolerance: float = 0.02) -> list[str]:
    errors: list[str] = []

    errors += _describe_violations(
        ~orders["channel"].isin(_VALID_CHANNELS), orders["order_id"], "Invalid channel value"
    )
    errors += _describe_violations(
        ~orders["status"].isin(_VALID_STATUSES), orders["order_id"], "Invalid status value"
    )
    errors += _describe_violations(
        ~orders["daypart"].isin(_VALID_DAYPARTS), orders["order_id"], "Invalid daypart value"
    )
    errors += _describe_violations(orders["subtotal"] < 0, orders["order_id"], "Negative subtotal")
    errors += _describe_violations(
        orders["preparation_minutes"] <= 0, orders["order_id"], "Non-positive preparation_minutes"
    )
    errors += _describe_violations(
        orders["order_timestamp"].isna(), orders["order_id"], "Missing order_timestamp"
    )

    expected_net_sales = (
        orders["subtotal"]
        - orders["discount_amount"]
        - orders["refund_amount"]
        - orders["platform_commission"]
    )
    reconciliation_gap = (orders["net_sales"] - expected_net_sales).abs()
    errors += _describe_violations(
        reconciliation_gap > monetary_tolerance,
        orders["order_id"],
        "net_sales does not reconcile to subtotal - discount - refund - commission",
    )

    dine_in_mask = orders["channel"] == "dine_in"
    errors += _describe_violations(
        dine_in_mask & orders["table_number"].isna(),
        orders["order_id"],
        "dine_in order missing table_number",
    )
    errors += _describe_violations(
        (~dine_in_mask) & orders["table_number"].notna(),
        orders["order_id"],
        "non-dine_in order has a table_number",
    )
    return errors


def validate_order_items(
    order_items: pd.DataFrame, valid_order_ids: set[str], valid_menu_item_ids: set[str]
) -> list[str]:
    errors: list[str] = []
    errors += _describe_violations(
        order_items["quantity"] <= 0, order_items["order_item_id"], "Non-positive quantity"
    )
    errors += _describe_violations(
        order_items["line_total"] < 0, order_items["order_item_id"], "Negative line_total"
    )
    errors += _describe_violations(
        ~order_items["order_id"].isin(valid_order_ids),
        order_items["order_item_id"],
        "order_id not found in orders",
    )
    errors += _describe_violations(
        ~order_items["menu_item_id"].isin(valid_menu_item_ids),
        order_items["order_item_id"],
        "menu_item_id not found in menu_items",
    )
    errors += _describe_violations(
        ~order_items["item_status"].isin(_VALID_ITEM_STATUSES),
        order_items["order_item_id"],
        "Invalid item_status value",
    )
    return errors


def validate_reviews(reviews: pd.DataFrame, valid_order_ids: set[str]) -> list[str]:
    if reviews.empty:
        return []
    errors: list[str] = []
    errors += _describe_violations(
        (reviews["rating"] < 1) | (reviews["rating"] > 5),
        reviews["review_id"],
        "Rating outside 1-5",
    )
    errors += _describe_violations(
        ~reviews["order_id"].isin(valid_order_ids),
        reviews["review_id"],
        "order_id not found in orders",
    )
    errors += _describe_violations(
        ~reviews["channel"].isin(_VALID_CHANNELS), reviews["review_id"], "Invalid channel value"
    )
    return errors


def validate_shifts(shifts: pd.DataFrame, valid_employee_ids: set[str]) -> list[str]:
    errors: list[str] = []
    errors += _describe_violations(
        shifts["shift_end"] <= shifts["shift_start"],
        shifts["shift_id"],
        "shift_end not after shift_start",
    )
    errors += _describe_violations(
        shifts["scheduled_hours"] <= 0, shifts["shift_id"], "Non-positive scheduled_hours"
    )
    errors += _describe_violations(
        shifts["actual_hours"] < 0, shifts["shift_id"], "Negative actual_hours"
    )
    errors += _describe_violations(
        shifts["labour_cost"] < 0, shifts["shift_id"], "Negative labour_cost"
    )
    errors += _describe_violations(
        shifts["absence_flag"] & (shifts["actual_hours"] != 0),
        shifts["shift_id"],
        "Absent shift has non-zero actual_hours",
    )
    errors += _describe_violations(
        ~shifts["employee_id"].isin(valid_employee_ids),
        shifts["shift_id"],
        "employee_id not found in employees",
    )
    return errors


def validate_inventory_movements(
    movements: pd.DataFrame, valid_ingredient_ids: set[str], balance_tolerance: float = 0.01
) -> list[str]:
    errors: list[str] = []
    errors += _describe_violations(
        ~movements["movement_type"].isin(_VALID_MOVEMENT_TYPES),
        movements["movement_id"],
        "Invalid movement_type value",
    )
    errors += _describe_violations(
        ~movements["ingredient_id"].isin(valid_ingredient_ids),
        movements["movement_id"],
        "ingredient_id not found in ingredients",
    )
    errors += _describe_violations(
        movements["unit_cost"] < 0, movements["movement_id"], "Negative unit_cost"
    )

    sorted_movements = movements.sort_values(["ingredient_id", "movement_timestamp"])
    running_balance = sorted_movements.groupby("ingredient_id")["quantity_change"].cumsum()
    negative_balance = running_balance < -balance_tolerance
    if negative_balance.any():
        examples = sorted_movements.loc[negative_balance, "movement_id"].head(5).tolist()
        errors.append(
            f"Running inventory balance went negative: {int(negative_balance.sum())} rows "
            f"(examples: {examples})"
        )
    return errors


def run_all_validations(
    daily_context: pd.DataFrame,
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    reviews: pd.DataFrame,
    valid_menu_item_ids: set[str],
    shifts: pd.DataFrame | None = None,
    valid_employee_ids: set[str] | None = None,
    movements: pd.DataFrame | None = None,
    valid_ingredient_ids: set[str] | None = None,
) -> dict[str, list[str]]:
    """Run every check and return errors grouped by table name."""
    valid_order_ids = set(orders["order_id"])
    results = {
        "daily_context": validate_daily_context(daily_context),
        "orders": validate_orders(orders),
        "order_items": validate_order_items(order_items, valid_order_ids, valid_menu_item_ids),
        "reviews": validate_reviews(reviews, valid_order_ids),
    }
    if shifts is not None and valid_employee_ids is not None:
        results["shifts"] = validate_shifts(shifts, valid_employee_ids)
    if movements is not None and valid_ingredient_ids is not None:
        results["inventory_movements"] = validate_inventory_movements(
            movements, valid_ingredient_ids
        )
    return results

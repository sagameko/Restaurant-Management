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


def run_all_validations(
    daily_context: pd.DataFrame,
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    reviews: pd.DataFrame,
    valid_menu_item_ids: set[str],
) -> dict[str, list[str]]:
    """Run every check and return errors grouped by table name."""
    valid_order_ids = set(orders["order_id"])
    return {
        "daily_context": validate_daily_context(daily_context),
        "orders": validate_orders(orders),
        "order_items": validate_order_items(order_items, valid_order_ids, valid_menu_item_ids),
        "reviews": validate_reviews(reviews, valid_order_ids),
    }

#!/usr/bin/env python
"""Generate a reproducible synthetic order/shift/inventory/review dataset.

Usage:
    uv run python scripts/generate_data.py \
        --start-date 2025-07-01 --days 365 --average-orders 100 --seed 42

The same seed always produces the same dataset (single `numpy.random.Generator`
seeded once, threaded through every generator function in a fixed call order:
daily context -> shifts -> orders/order items -> reviews -> inventory movements).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from restaurant_ops.config import RAW_DIR, get_business_rules, get_simulation_settings
from restaurant_ops.generation.inventory import generate_inventory_movements
from restaurant_ops.generation.orders import generate_orders_and_items
from restaurant_ops.generation.reviews import generate_reviews
from restaurant_ops.generation.staffing import generate_shifts
from restaurant_ops.generation.weather import generate_daily_context
from restaurant_ops.ingestion.loader import (
    load_employees,
    load_ingredients,
    load_menu_items,
    load_recipes,
    load_suppliers,
    validate_referential_integrity,
)
from restaurant_ops.logging_config import get_logger
from restaurant_ops.validation.rules import run_all_validations

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="YYYY-MM-DD, defaults to config/simulation.yaml",
    )
    parser.add_argument("--days", type=int, default=None, help="Number of days to simulate")
    parser.add_argument("--average-orders", type=int, default=None, help="Average orders per day")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument(
        "--output-dir", type=Path, default=RAW_DIR, help="Where to write the generated CSVs"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    simulation_settings = get_simulation_settings()
    business_rules = get_business_rules()

    start_date = (
        date.fromisoformat(args.start_date)
        if args.start_date
        else date.fromisoformat(simulation_settings.simulation.start_date)
    )
    number_of_days = args.days or simulation_settings.simulation.number_of_days
    average_daily_orders = (
        args.average_orders or simulation_settings.simulation.average_daily_orders
    )
    seed = args.seed if args.seed is not None else simulation_settings.simulation.random_seed

    end_date = start_date + timedelta(days=number_of_days - 1)
    logger.info("Generating %s days from %s (seed=%s)", number_of_days, start_date, seed)

    menu_items = load_menu_items()
    ingredients = load_ingredients()
    suppliers = load_suppliers()
    recipes = load_recipes()
    employees = load_employees()
    validate_referential_integrity(menu_items, ingredients, suppliers, recipes)

    rng = np.random.default_rng(seed)

    daily_context = generate_daily_context(start_date, number_of_days, business_rules, rng)
    shifts, staffing_lookup = generate_shifts(daily_context, employees, business_rules, rng)
    orders, order_items = generate_orders_and_items(
        daily_context,
        menu_items,
        ingredients,
        recipes,
        simulation_settings,
        business_rules,
        rng,
        staffing_lookup,
        average_daily_orders=average_daily_orders,
    )
    reviews = generate_reviews(orders, end_date, business_rules, rng)
    inventory_movements = generate_inventory_movements(
        daily_context, orders, order_items, ingredients, suppliers, recipes, business_rules, rng
    )

    validation_errors = run_all_validations(
        daily_context,
        orders,
        order_items,
        reviews,
        {item.menu_item_id for item in menu_items},
        shifts=shifts,
        valid_employee_ids={e.employee_id for e in employees},
        movements=inventory_movements,
        valid_ingredient_ids={i.ingredient_id for i in ingredients},
    )
    total_failures = sum(len(errors) for errors in validation_errors.values())

    args.output_dir.mkdir(parents=True, exist_ok=True)
    daily_context.to_csv(args.output_dir / "daily_context.csv", index=False)
    orders.to_csv(args.output_dir / "orders.csv", index=False)
    order_items.to_csv(args.output_dir / "order_items.csv", index=False)
    reviews.to_csv(args.output_dir / "reviews.csv", index=False)
    shifts.to_csv(args.output_dir / "employee_shifts.csv", index=False)
    inventory_movements.to_csv(args.output_dir / "inventory_movements.csv", index=False)

    print("Synthetic data generation completed")
    print(f"Generated at: {datetime.now().isoformat(timespec='seconds')}")
    print(f"Days simulated: {number_of_days} ({start_date} to {end_date})")
    print(f"Random seed: {seed}")
    print(f"Daily context rows: {len(daily_context):,}")
    print(f"Orders generated: {len(orders):,}")
    print(f"Order items generated: {len(order_items):,}")
    print(f"Reviews generated: {len(reviews):,}")
    print(f"Employee shifts generated: {len(shifts):,}")
    print(f"Inventory movements generated: {len(inventory_movements):,}")
    print(f"Validation failures: {total_failures}")
    if total_failures:
        for table, errors in validation_errors.items():
            for error in errors:
                print(f"  [{table}] {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

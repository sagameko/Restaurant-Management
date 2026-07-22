# Restaurant Operations Intelligence Platform

An end-to-end restaurant data platform that simulates realistic operational
data, transforms it into reliable analytical models, and presents
actionable insights through an interactive Streamlit application.

The central project question:

> How can restaurant order, staffing, inventory, menu and customer-experience
> data be combined to improve daily operational decisions?

## Disclaimer

This project uses synthetic operational data generated from configurable
business rules. Menu names and publicly listed prices are used only as
reference material. No confidential customer, employee, supplier, recipe,
financial or transaction data is included. This project is not affiliated
with Bon Bon Boy and does not use confidential business information.

## Status

Work in progress. Implemented so far: seed data (menu, ingredients,
suppliers, recipes, employees) with referential-integrity validation and
estimated food-cost calculation per menu item; a full synthetic
generation pipeline (daily weather/calendar context, employee shifts,
orders, order items, customer reviews, and inventory movements) with
demand, channel, kitchen-load, staffing/absence, and inventory-reorder
relationships driven by `config/business_rules.yaml`. DuckDB + dbt
transformations, the Streamlit dashboard and demand forecasting are still
to come. See `docs/limitations.md` for what the synthetic data does and
doesn't represent.

## Setup

```bash
uv sync
uv run pytest
```

## Seed data

`data/seed/` contains the manually maintained, relatively stable business
entities: `menu_items.csv`, `ingredients.csv`, `suppliers.csv`,
`recipes.csv` and `employees.csv`. All costs, suppliers, recipe
quantities and staff details are synthetic estimates; menu item
names/categories/prices are a representative, illustrative Vietnamese
menu and are not scraped or copied from any live site.

Validate the seed data and print an estimated food-cost summary:

```bash
uv run python -c "
from restaurant_ops.ingestion.loader import (
    load_menu_items, load_ingredients, load_suppliers, load_recipes,
    validate_referential_integrity, build_seed_report,
)
menu_items = load_menu_items()
ingredients = load_ingredients()
suppliers = load_suppliers()
recipes = load_recipes()
validate_referential_integrity(menu_items, ingredients, suppliers, recipes)
print(build_seed_report(menu_items, ingredients, recipes))
"
```

## Generating synthetic operational data

```bash
uv run python scripts/generate_data.py --start-date 2025-07-01 --days 365 --average-orders 100 --seed 42
```

Writes `data/raw/daily_context.csv`, `employee_shifts.csv`, `orders.csv`,
`order_items.csv`, `reviews.csv` and `inventory_movements.csv`. The same
seed always reproduces the same dataset. See `docs/business_rules.md`
for the demand/channel/staffing/inventory/review model, and
`docs/data_dictionary.md` for the table schemas.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

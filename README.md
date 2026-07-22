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
suppliers, recipes), referential-integrity validation, and estimated
food-cost calculation per menu item. Synthetic order generation, DuckDB +
dbt transformations, the Streamlit dashboard and demand forecasting are
still to come.

## Setup

```bash
uv sync
uv run pytest
```

## Seed data

`data/seed/` contains the manually maintained, relatively stable business
entities: `menu_items.csv`, `ingredients.csv`, `suppliers.csv` and
`recipes.csv`. All costs, suppliers and recipe quantities are synthetic
estimates; menu item names/categories/prices are a representative,
illustrative Vietnamese menu and are not scraped or copied from any live
site.

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

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

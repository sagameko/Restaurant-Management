# Restaurant Operations Intelligence Platform

[![CI](https://github.com/sagameko/Restaurant-Management/actions/workflows/ci.yml/badge.svg)](https://github.com/sagameko/Restaurant-Management/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![uv](https://img.shields.io/badge/managed%20with-uv-DE5FE9)
![DuckDB](https://img.shields.io/badge/warehouse-DuckDB-FFF000?logo=duckdb&logoColor=black)
![dbt](https://img.shields.io/badge/transform-dbt-FF694B?logo=dbt&logoColor=white)
![Streamlit](https://img.shields.io/badge/app-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![Ruff](https://img.shields.io/badge/lint%2Fformat-Ruff-D7FF64?logo=ruff&logoColor=black)
![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)

A restaurant doesn't run on one spreadsheet — it runs on the collision of
orders, staffing, inventory, weather, and how customers actually felt
about their food. This project builds that whole story from scratch: a
synthetic Vietnamese restaurant, simulated day by day for a year, whose
data actually behaves the way a real kitchen does — get busy enough and
prep times climb, ratings dip, and stock runs thin.

It's a full pipeline, not a notebook: a reproducible Python data
generator with real operational logic, a dbt-on-DuckDB warehouse with a
proper star schema, and a Streamlit app that turns all of it into
decisions a restaurant manager could actually use.

The central project question:

> How can restaurant order, staffing, inventory, menu and customer-experience
> data be combined to improve daily operational decisions?

## Demo

```bash
uv sync
uv run streamlit run app/Home.py
```

Opens at `http://localhost:8501`. The dashboard reads from the dbt-built
warehouse (`data/database/restaurant.duckdb`) — if it isn't built yet,
see [Generating synthetic operational data](#generating-synthetic-operational-data)
and [Loading into DuckDB and running dbt](#loading-into-duckdb-and-running-dbt)
below first.

| Executive Overview | Menu Engineering |
|---|---|
| ![Executive Overview](docs/screenshots/executive_overview.png) | ![Menu Engineering](docs/screenshots/menu_engineering.png) |

| Channel Profitability | Inventory Risk |
|---|---|
| ![Channel Profitability](docs/screenshots/channel_profitability.png) | ![Inventory Risk](docs/screenshots/inventory_risk.png) |

Three more pages not pictured — Service Performance, Labour Productivity,
Customer Experience — follow the same pattern. All data shown is
synthetic; see the disclaimer below.

## Disclaimer

This project uses synthetic operational data generated from configurable
business rules. Menu names and publicly listed prices are used only as
reference material. No confidential customer, employee, supplier, recipe,
financial or transaction data is included. This project is not affiliated
with Bon Bon Boy and does not use confidential business information.

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Language & tooling | Python 3.12, [uv](https://docs.astral.sh/uv/) | Fast, modern dependency management — no separate pip/venv/poetry dance. |
| Data generation | pandas, NumPy | A seeded `numpy.random.Generator` threaded through every generator function makes the whole year reproducible from one `--seed`. |
| Validation | Pydantic v2 | Seed data (menu, ingredients, employees...) is validated row-by-row on load; generated tables use vectorised pandas checks at scale. |
| Warehouse | [DuckDB](https://duckdb.org/) | Single-file, zero-config, embedded OLAP engine — no server to run for ~170k rows of synthetic data. |
| Transformation | [dbt](https://www.getdbt.com/) | Layered SQL (staging → intermediate → dimensions/facts → marts), with dependency resolution, testing, and docs built in. |
| App | [Streamlit](https://streamlit.io/) + Plotly | Eight pages reading straight from the dbt marts. |
| Forecasting | [scikit-learn](https://scikit-learn.org/) | Naive/moving-average baselines vs. linear regression and random forest, time-based validated. |
| Quality | pytest, [Ruff](https://docs.astral.sh/ruff/) | 77 tests including an end-to-end pipeline test; Ruff replaces flake8 + isort + black + pyupgrade in one fast tool. |
| CI | GitHub Actions | Lint → test → generate → load → `dbt build` → verify marts, on every PR. |

See `docs/architecture.md` for how the pieces actually fit together, and
`docs/business_rules.md` for the (surprisingly deep) business logic
behind the synthetic data.

## Status

Work in progress. Implemented so far: seed data (menu, ingredients,
suppliers, recipes, employees) with referential-integrity validation and
estimated food-cost calculation per menu item; a full synthetic
generation pipeline (daily weather/calendar context, employee shifts,
orders, order items, customer reviews, and inventory movements) with
demand, channel, kitchen-load, staffing/absence, and inventory-reorder
relationships driven by `config/business_rules.yaml`; a complete
DuckDB + dbt transformation layer (staging → intermediate →
dimensions/facts → 7 analytical marts, 98 passing dbt checks); an 8-page
Streamlit dashboard reading from that warehouse (`app/`); and a daily
order-volume forecast (naive, moving-average, linear regression, and
random-forest candidates, time-based validated, with a 7-day-ahead
forecast and a staffing recommendation). See `docs/limitations.md` for
what the synthetic data does and doesn't represent, and
`docs/architecture.md` for how the pieces fit together.

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

## Loading into DuckDB and running dbt

```bash
uv run python scripts/load_raw_data.py
cp dbt_restaurant/profiles.yml.example dbt_restaurant/profiles.yml  # first time only
uv run dbt build --project-dir dbt_restaurant --profiles-dir dbt_restaurant
```

Always run dbt from the repository root with `--profiles-dir
dbt_restaurant` — see `docs/architecture.md` for why. Browse the star
schema and column-level docs with:

```bash
uv run dbt docs generate --project-dir dbt_restaurant --profiles-dir dbt_restaurant
uv run dbt docs serve --project-dir dbt_restaurant --profiles-dir dbt_restaurant
```

## Running the dashboard

```bash
uv run streamlit run app/Home.py
```

Eight pages (Executive Overview, Menu Engineering, Channel Profitability,
Service Performance, Labour Productivity, Inventory Risk, Customer
Experience, Demand Forecast), all reading from the dbt-built warehouse —
none of them touch the raw CSVs directly. See `docs/architecture.md` for
which pages read straight from a mart and which also query the
underlying fact/dim tables for grain no mart carries.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

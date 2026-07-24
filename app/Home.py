"""Landing page for the Restaurant Operations Intelligence Platform."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402
from components.database import get_connection  # noqa: E402

st.set_page_config(
    page_title="Restaurant Ops Intelligence",
    page_icon="🍜",
    layout="wide",
)

st.title("Restaurant Operations Intelligence Platform")

st.warning(
    "**All data in this application is synthetic.** Orders, staffing, "
    "inventory, and customer reviews are generated from configurable "
    "business rules — not real transactions, employees, or customers. "
    "See the project README for details.",
    icon="⚠️",
)

st.markdown(
    """
A restaurant doesn't run on one spreadsheet — it runs on the collision of
orders, staffing, inventory, weather, and how customers actually felt
about their food. This dashboard turns a year of simulated Vietnamese
restaurant operations into the kind of view a manager would actually use
to make decisions.

Every page below reads from the dbt-built analytical warehouse
(`data/database/restaurant.duckdb`), not from raw files.
"""
)

try:
    get_connection().execute("select 1").fetchone()
    st.success("Connected to the warehouse.", icon="✅")
except Exception as exc:  # noqa: BLE001
    st.error(
        "Could not connect to the warehouse. Run `uv run python "
        "scripts/generate_data.py`, `uv run python scripts/load_raw_data.py`, "
        "and `uv run dbt build --project-dir dbt_restaurant "
        f"--profiles-dir dbt_restaurant` first.\n\n{exc}"
    )

st.subheader("Pages")

st.markdown(
    """
1. **Executive Overview** — daily sales, margin, service, and rating KPIs, with a summary.
2. **Menu Engineering** — Stars/Plowhorses/Puzzles/Dogs, plus per-item demand drill-down.
3. **Channel Profitability** — Dine-In vs. Pickup vs. Uber Eats vs. DoorDash, revenue vs. profit.
4. **Service Performance** — prep time, lateness, kitchen load, and an hourly-by-weekday heatmap.
5. **Labour Productivity** — labour cost, hours, and staffing-level flags by date and daypart.
6. **Inventory Risk** — reorder alerts, stock days remaining, waste, and affected menu items.
7. **Customer Experience** — ratings, complaints, and the reviews behind them.
"""
)

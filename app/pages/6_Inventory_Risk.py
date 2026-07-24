"""Page 6: Inventory Risk."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402
from components.charts import CATEGORICAL, STATUS, style_fig  # noqa: E402
from components.database import load_mart  # noqa: E402
from components.filters import (  # noqa: E402
    apply_filters,
    format_currency,
    format_number,
    kpi_row,
    render_sidebar_filters,
)

st.set_page_config(page_title="Inventory Risk", page_icon="🍜", layout="wide")
st.title("Inventory Risk")

inventory = load_mart("mart_inventory_risk")

filters = render_sidebar_filters(
    inventory, category_column="ingredient_category", key_prefix="inventory"
)
inventory_f = apply_filters(inventory, filters, category_column="ingredient_category")

if inventory_f.empty:
    st.info("No ingredients in the selected category filter.")
    st.stop()

kpi_row(
    {
        "Closing stock value": format_currency(inventory_f["closing_value"].sum()),
        "Reorder alerts": format_number(inventory_f["is_reorder_alert"].sum()),
        "Waste value": format_currency(inventory_f["total_waste_value"].sum()),
        "Avg days of stock left": f"{inventory_f['estimated_days_of_stock_remaining'].mean():.1f}",
    }
)

st.divider()

st.subheader("Reorder alerts")
alerts = inventory_f[inventory_f["is_reorder_alert"]].sort_values(
    "estimated_days_of_stock_remaining"
)
if alerts.empty:
    st.success("No ingredients are currently below their reorder level.", icon="✅")
else:
    display = alerts[
        [
            "ingredient_name",
            "ingredient_category",
            "closing_quantity",
            "reorder_level",
            "estimated_days_of_stock_remaining",
            "supplier_name",
            "supplier_lead_time_days",
            "affected_menu_items",
        ]
    ].copy()
    st.dataframe(display, hide_index=True, use_container_width=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Closing stock value by category")
    by_category = inventory_f.groupby("ingredient_category", as_index=False)["closing_value"].sum()
    fig = px.bar(
        by_category.sort_values("closing_value", ascending=False),
        x="ingredient_category",
        y="closing_value",
        color="ingredient_category",
        color_discrete_sequence=CATEGORICAL,
    )
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

with col2:
    st.subheader("Most waste-prone ingredients")
    top_waste = inventory_f.nlargest(10, "total_waste_value")
    fig = px.bar(
        top_waste.sort_values("total_waste_value"),
        x="total_waste_value",
        y="ingredient_name",
        orientation="h",
        color_discrete_sequence=[STATUS["serious"]],
    )
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

st.subheader("Estimated days of stock remaining")
fig = px.bar(
    inventory_f.nsmallest(20, "estimated_days_of_stock_remaining").sort_values(
        "estimated_days_of_stock_remaining"
    ),
    x="ingredient_name",
    y="estimated_days_of_stock_remaining",
    color="is_reorder_alert",
    color_discrete_map={True: STATUS["critical"], False: CATEGORICAL[0]},
)
st.plotly_chart(style_fig(fig), use_container_width=True)

emergency_deliveries = format_number(inventory_f["emergency_delivery_count"].sum())
expired_value = format_currency(inventory_f["total_expired_value"].sum())
st.caption(
    f"Emergency deliveries in period: {emergency_deliveries} · Expired stock value: {expired_value}"
)

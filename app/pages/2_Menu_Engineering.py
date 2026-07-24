"""Page 2: Menu Engineering."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402
from components.charts import CATEGORICAL, style_fig  # noqa: E402
from components.database import (  # noqa: E402
    item_channel_distribution,
    item_demand_by_hour,
    item_demand_by_temperature,
    load_mart,
)
from components.filters import (  # noqa: E402
    apply_filters,
    format_currency,
    format_number,
    format_pct,
    render_sidebar_filters,
)

st.set_page_config(page_title="Menu Engineering", page_icon="🍜", layout="wide")
st.title("Menu Engineering")

menu = load_mart("mart_menu_engineering")

filters = render_sidebar_filters(menu, category_column="category", key_prefix="menu")
menu_f = apply_filters(menu, filters, category_column="category")

if menu_f.empty:
    st.info("No items in the selected category filter.")
    st.stop()

CLASSIFICATION_COLORS = {
    "Star": CATEGORICAL[0],
    "Plowhorse": CATEGORICAL[1],
    "Puzzle": CATEGORICAL[2],
    "Dog": CATEGORICAL[3],
}

st.subheader("Menu-engineering matrix")
fig = px.scatter(
    menu_f,
    x="units_sold",
    y="contribution_margin_pct",
    color="menu_engineering_classification",
    color_discrete_map=CLASSIFICATION_COLORS,
    hover_name="item_name",
    hover_data={"category": True, "revenue": ":$,.0f"},
    labels={"units_sold": "Units sold", "contribution_margin_pct": "Contribution margin %"},
)
fig.add_vline(x=menu_f["units_sold"].median(), line_dash="dot", line_color="#898781")
fig.add_hline(y=menu_f["contribution_margin_pct"].median(), line_dash="dot", line_color="#898781")
st.plotly_chart(style_fig(fig), use_container_width=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("**Best-selling items**")
    st.dataframe(
        menu_f.nlargest(8, "units_sold")[["item_name", "units_sold"]],
        hide_index=True,
        use_container_width=True,
    )

with col2:
    st.markdown("**Highest-margin items**")
    st.dataframe(
        menu_f.nlargest(8, "contribution_margin_pct")[
            ["item_name", "contribution_margin_pct"]
        ].assign(contribution_margin_pct=lambda d: d["contribution_margin_pct"].map(format_pct)),
        hide_index=True,
        use_container_width=True,
    )

with col3:
    st.markdown("**High-sales, low-margin (Plowhorse)**")
    plowhorse = menu_f[menu_f["menu_engineering_classification"] == "Plowhorse"]
    st.dataframe(
        plowhorse.nlargest(8, "units_sold")[["item_name", "units_sold"]],
        hide_index=True,
        use_container_width=True,
    )

with col4:
    st.markdown("**Low-sales, high-margin (Puzzle)**")
    puzzle = menu_f[menu_f["menu_engineering_classification"] == "Puzzle"]
    st.dataframe(
        puzzle.nlargest(8, "contribution_margin_pct")[
            ["item_name", "contribution_margin_pct"]
        ].assign(contribution_margin_pct=lambda d: d["contribution_margin_pct"].map(format_pct)),
        hide_index=True,
        use_container_width=True,
    )

st.subheader("Category comparison")
by_category = menu_f.groupby("category", as_index=False).agg(
    revenue=("revenue", "sum"),
    estimated_contribution_margin=("estimated_contribution_margin", "sum"),
)
fig = px.bar(
    by_category.sort_values("revenue", ascending=False),
    x="category",
    y=["revenue", "estimated_contribution_margin"],
    barmode="group",
    color_discrete_sequence=CATEGORICAL,
)
st.plotly_chart(style_fig(fig), use_container_width=True)

st.divider()
st.subheader("Item drill-down")

selected_name = st.selectbox("Select a menu item", sorted(menu_f["item_name"].unique()))
item = menu_f[menu_f["item_name"] == selected_name].iloc[0]

per_unit_cost = item["estimated_food_cost"] / item["units_sold"] if item["units_sold"] else None

kpi_cols = st.columns(4)
kpi_cols[0].metric("Price", format_currency(item["selling_price"]))
kpi_cols[1].metric("Estimated cost / unit", format_currency(per_unit_cost))
kpi_cols[2].metric("Estimated margin", format_pct(item["contribution_margin_pct"]))
kpi_cols[3].metric("Units sold", format_number(item["units_sold"]))

drill_col1, drill_col2, drill_col3 = st.columns(3)

with drill_col1:
    st.markdown("**Channel distribution**")
    dist = item_channel_distribution(item["menu_item_id"])
    fig = px.pie(dist, names="channel", values="quantity", color_discrete_sequence=CATEGORICAL)
    st.plotly_chart(style_fig(fig), use_container_width=True)

with drill_col2:
    st.markdown("**Demand by hour**")
    by_hour = item_demand_by_hour(item["menu_item_id"])
    fig = px.bar(by_hour, x="order_hour", y="quantity", color_discrete_sequence=CATEGORICAL)
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

with drill_col3:
    st.markdown("**Demand by temperature group**")
    by_temp = item_demand_by_temperature(item["menu_item_id"])
    fig = px.bar(by_temp, x="temperature_band", y="quantity", color_discrete_sequence=CATEGORICAL)
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

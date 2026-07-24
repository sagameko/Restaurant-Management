"""Page 1: Executive Overview."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402
from components.charts import CATEGORICAL, style_fig  # noqa: E402
from components.database import (  # noqa: E402
    load_mart,
    prep_time_vs_promised_by_daypart,
)
from components.filters import (  # noqa: E402
    apply_filters,
    format_currency,
    format_minutes,
    format_number,
    format_pct,
    kpi_row,
    render_sidebar_filters,
)
from components.insights import daily_performance_summary  # noqa: E402

st.set_page_config(page_title="Executive Overview", page_icon="🍜", layout="wide")
st.title("Executive Overview")

daily = load_mart("mart_daily_performance")
service = load_mart("mart_service_quality")
channel = load_mart("mart_channel_profitability")
menu = load_mart("mart_menu_engineering")

filters = render_sidebar_filters(daily, date_column="business_date", key_prefix="exec")
daily_f = apply_filters(daily, filters, date_column="business_date")
service_f = apply_filters(service, filters, date_column="business_date")

if daily_f.empty:
    st.info("No data in the selected date range.")
    st.stop()

st.info(daily_performance_summary(prep_time_vs_promised_by_daypart()), icon="📋")

kpi_row(
    {
        "Net sales": format_currency(daily_f["net_sales"].sum()),
        "Orders": format_number(daily_f["order_count"].sum()),
        "Avg order value": format_currency(daily_f["average_order_value"].mean()),
        "Gross margin": format_pct(daily_f["estimated_gross_margin_pct"].mean()),
    }
)
kpi_row(
    {
        "Labour cost %": format_pct(daily_f["labour_cost_pct"].mean()),
        "Avg prep time": format_minutes(daily_f["average_preparation_minutes"].mean()),
        "Avg rating": f"{daily_f['average_rating'].mean():.2f} / 5",
        "Waste cost": format_currency(daily_f["waste_cost"].sum()),
    }
)

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Daily net-sales trend")
    fig = px.line(daily_f.sort_values("business_date"), x="business_date", y="net_sales")
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

with col2:
    st.subheader("Orders by daypart")
    by_daypart = service_f.groupby("daypart", as_index=False)["order_count"].sum()
    fig = px.bar(
        by_daypart,
        x="daypart",
        y="order_count",
        color="daypart",
        color_discrete_sequence=CATEGORICAL,
    )
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    st.subheader("Net sales by channel")
    fig = px.bar(
        channel.sort_values("net_sales", ascending=False),
        x="channel_label",
        y="net_sales",
        color="channel_label",
        color_discrete_sequence=CATEGORICAL,
    )
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

with col4:
    st.subheader("Estimated gross profit by category")
    by_category = (
        menu.groupby("category", as_index=False)["estimated_contribution_margin"]
        .sum()
        .sort_values("estimated_contribution_margin", ascending=False)
    )
    fig = px.bar(
        by_category,
        x="category",
        y="estimated_contribution_margin",
        color="category",
        color_discrete_sequence=CATEGORICAL,
    )
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

st.subheader("Preparation time over time")
fig = px.line(
    daily_f.sort_values("business_date"), x="business_date", y="average_preparation_minutes"
)
st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

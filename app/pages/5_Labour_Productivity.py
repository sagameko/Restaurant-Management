"""Page 5: Labour Productivity."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402
from components.charts import CATEGORICAL, style_fig  # noqa: E402
from components.database import load_mart  # noqa: E402
from components.filters import (  # noqa: E402
    apply_filters,
    format_currency,
    format_number,
    format_pct,
    kpi_row,
    render_sidebar_filters,
)

st.set_page_config(page_title="Labour Productivity", page_icon="🍜", layout="wide")
st.title("Labour Productivity")

labour = load_mart("mart_labour_productivity")

filters = render_sidebar_filters(labour, date_column="business_date", key_prefix="labour")
labour_f = apply_filters(labour, filters, date_column="business_date")

if labour_f.empty:
    st.info("No data in the selected date range.")
    st.stop()

kpi_row(
    {
        "Labour cost": format_currency(labour_f["total_labour_cost"].sum()),
        "Labour hours": f"{labour_f['total_actual_hours'].sum():,.0f} hrs",
        "Revenue / labour hr": format_currency(labour_f["revenue_per_labour_hour"].mean()),
        "Orders / labour hr": f"{labour_f['orders_per_labour_hour'].mean():.2f}",
        "Labour cost %": format_pct(labour_f["labour_cost_pct"].mean()),
    }
)

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Actual vs. scheduled hours")
    trend = labour_f.groupby("business_date", as_index=False).agg(
        Scheduled=("total_scheduled_hours", "sum"),
        Actual=("total_actual_hours", "sum"),
    )
    fig = px.line(
        trend, x="business_date", y=["Scheduled", "Actual"], color_discrete_sequence=CATEGORICAL
    )
    st.plotly_chart(style_fig(fig), use_container_width=True)

with col2:
    st.subheader("Labour cost % by daypart")
    fig = px.box(
        labour_f,
        x="daypart",
        y="labour_cost_pct",
        color="daypart",
        color_discrete_sequence=CATEGORICAL,
    )
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

st.subheader("Staffing-level windows")
st.caption(
    "Understaffed = average kitchen-load ratio above 1.2. Overstaffed = below "
    "0.5. Balanced otherwise."
)
tab1, tab2 = st.tabs(["Understaffed", "Overstaffed"])

with tab1:
    understaffed = labour_f[labour_f["staffing_level_flag"] == "Understaffed"].sort_values(
        "avg_kitchen_load_ratio", ascending=False
    )
    st.dataframe(
        understaffed[
            [
                "business_date",
                "daypart",
                "avg_kitchen_load_ratio",
                "order_count",
                "total_actual_hours",
            ]
        ].head(15),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(f"{len(understaffed)} understaffed windows in the selected range.")

with tab2:
    overstaffed = labour_f[labour_f["staffing_level_flag"] == "Overstaffed"].sort_values(
        "avg_kitchen_load_ratio"
    )
    st.dataframe(
        overstaffed[
            [
                "business_date",
                "daypart",
                "avg_kitchen_load_ratio",
                "order_count",
                "total_actual_hours",
            ]
        ].head(15),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(f"{len(overstaffed)} overstaffed windows in the selected range.")

st.subheader("Productivity: orders per labour hour, kitchen vs. front-of-house")
fig = px.scatter(
    labour_f,
    x="orders_per_kitchen_labour_hour",
    y="orders_per_front_of_house_labour_hour",
    color="daypart",
    size="order_count",
    color_discrete_sequence=CATEGORICAL,
    hover_data={"business_date": True},
)
st.plotly_chart(style_fig(fig), use_container_width=True)

shifts = format_number(labour_f["scheduled_shift_count"].sum())
absences = format_number(labour_f["absence_count"].sum())
st.caption(f"Total scheduled shifts: {shifts} · Absences: {absences}")

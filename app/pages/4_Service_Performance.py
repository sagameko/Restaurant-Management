"""Page 4: Service Performance."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402
from components.charts import CATEGORICAL, style_fig  # noqa: E402
from components.database import hourly_heatmap_by_weekday, load_mart  # noqa: E402
from components.filters import (  # noqa: E402
    apply_filters,
    format_minutes,
    format_number,
    format_pct,
    kpi_row,
    render_sidebar_filters,
)

st.set_page_config(page_title="Service Performance", page_icon="🍜", layout="wide")
st.title("Service Performance")

service = load_mart("mart_service_quality")
labour = load_mart("mart_labour_productivity")

filters = render_sidebar_filters(service, date_column="business_date", key_prefix="service")
service_f = apply_filters(service, filters, date_column="business_date")

if service_f.empty:
    st.info("No data in the selected date range.")
    st.stop()


def weighted_avg(col: str) -> float:
    return (service_f[col] * service_f["order_count"]).sum() / service_f["order_count"].sum()


kpi_row(
    {
        "Orders": format_number(service_f["order_count"].sum()),
        "Late orders": format_pct(weighted_avg("late_order_pct")),
        "Missing items": format_pct(weighted_avg("missing_item_pct")),
        "Refunds": format_pct(weighted_avg("refund_pct")),
    }
)

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Preparation-time distribution by daypart")
    by_daypart = service_f.groupby("daypart", as_index=False).agg(
        Average=("average_preparation_minutes", "mean"),
        Median=("median_preparation_minutes", "mean"),
        P90=("p90_preparation_minutes", "mean"),
    )
    fig = px.bar(
        by_daypart,
        x="daypart",
        y=["Average", "Median", "P90"],
        barmode="group",
        color_discrete_sequence=CATEGORICAL,
        labels={"value": "Minutes", "daypart": "Daypart", "variable": ""},
    )
    st.plotly_chart(style_fig(fig), use_container_width=True)

with col2:
    st.subheader("Kitchen-load relationship")
    fig = px.scatter(
        service_f,
        x="average_kitchen_load_ratio",
        y="average_preparation_minutes",
        color="daypart",
        color_discrete_sequence=CATEGORICAL,
        labels={
            "average_kitchen_load_ratio": "Kitchen load ratio",
            "average_preparation_minutes": "Avg prep (min)",
        },
    )
    st.plotly_chart(style_fig(fig), use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    st.subheader("Peak service windows")
    st.caption("Highest kitchen-load business-date / daypart combinations.")
    peak = service_f.nlargest(10, "peak_kitchen_load_ratio")[
        [
            "business_date",
            "daypart",
            "peak_kitchen_load_ratio",
            "average_preparation_minutes",
            "order_count",
        ]
    ].copy()
    peak["average_preparation_minutes"] = peak["average_preparation_minutes"].map(format_minutes)
    st.dataframe(peak, hide_index=True, use_container_width=True)

with col4:
    st.subheader("Service outcomes by staffing level")
    merged = service_f.merge(
        labour[["business_date", "daypart", "staffing_level_flag"]], on=["business_date", "daypart"]
    )
    by_flag = merged.groupby("staffing_level_flag", as_index=False).agg(
        late_order_pct=("late_order_pct", "mean"),
        missing_item_pct=("missing_item_pct", "mean"),
        refund_pct=("refund_pct", "mean"),
    )
    fig = px.bar(
        by_flag,
        x="staffing_level_flag",
        y=["late_order_pct", "missing_item_pct", "refund_pct"],
        barmode="group",
        color_discrete_sequence=CATEGORICAL,
        labels={"value": "Rate", "staffing_level_flag": "Staffing level", "variable": ""},
    )
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(style_fig(fig), use_container_width=True)

st.divider()
st.subheader("Hourly demand heatmap by weekday")
heatmap = hourly_heatmap_by_weekday()
weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
pivot = heatmap.pivot(index="day_name", columns="order_hour", values="order_count").reindex(
    weekday_order
)
fig = px.imshow(
    pivot,
    color_continuous_scale=["#fcfcfb", "#6da7ec", "#0d366b"],
    labels={"x": "Hour of day", "y": "", "color": "Orders"},
    aspect="auto",
)
st.plotly_chart(style_fig(fig), use_container_width=True)

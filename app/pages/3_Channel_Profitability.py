"""Page 3: Channel Profitability."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402
from components.charts import CATEGORICAL, style_fig  # noqa: E402
from components.database import load_mart  # noqa: E402
from components.filters import format_currency, format_minutes  # noqa: E402

st.set_page_config(page_title="Channel Profitability", page_icon="🍜", layout="wide")
st.title("Channel Profitability")
st.caption("Dine-In · Pickup · Uber Eats · DoorDash")

channel = load_mart("mart_channel_profitability").sort_values("net_sales", ascending=False)

st.subheader("Revenue is not profit")
st.caption(
    "Gross sales is what customers paid. Estimated gross profit is what's left "
    "after commission and refunds — delivery channels can out-sell dine-in on "
    "gross sales while returning far less to the business."
)
fig = px.bar(
    channel,
    x="channel_label",
    y=["gross_sales", "estimated_gross_profit"],
    barmode="group",
    color_discrete_sequence=CATEGORICAL,
    labels={"value": "$", "channel_label": "Channel", "variable": ""},
)
st.plotly_chart(style_fig(fig), use_container_width=True)

st.subheader("Channel comparison")
display = channel[
    [
        "channel_label",
        "order_count",
        "gross_sales",
        "commission",
        "refunds",
        "net_sales",
        "estimated_gross_profit",
        "average_order_value",
        "average_preparation_minutes",
        "average_rating",
    ]
].copy()
for col in [
    "gross_sales",
    "commission",
    "refunds",
    "net_sales",
    "estimated_gross_profit",
    "average_order_value",
]:
    display[col] = display[col].map(format_currency)
display["average_preparation_minutes"] = display["average_preparation_minutes"].map(format_minutes)
display["average_rating"] = display["average_rating"].map(lambda x: f"{x:.2f} / 5")
st.dataframe(display, hide_index=True, use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Commission as a share of gross sales")
    channel["commission_share"] = channel["commission"] / channel["gross_sales"]
    fig = px.bar(
        channel,
        x="channel_label",
        y="commission_share",
        color="channel_label",
        color_discrete_sequence=CATEGORICAL,
    )
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

with col2:
    st.subheader("Late-order % and average rating")
    fig = px.bar(
        channel,
        x="channel_label",
        y="late_order_pct",
        color="channel_label",
        color_discrete_sequence=CATEGORICAL,
    )
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

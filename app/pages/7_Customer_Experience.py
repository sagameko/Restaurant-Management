"""Page 7: Customer Experience."""

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
    format_number,
    format_pct,
    kpi_row,
    render_sidebar_filters,
)

st.set_page_config(page_title="Customer Experience", page_icon="🍜", layout="wide")
st.title("Customer Experience")

st.warning(
    "All reviews shown on this page are **synthetic** — generated from a "
    "rating formula and templated text, not written by real customers.",
    icon="⚠️",
)

reviews = load_mart("mart_review_analysis")

filters = render_sidebar_filters(
    reviews, date_column="business_date", channel_column="channel", key_prefix="reviews"
)
reviews_f = apply_filters(reviews, filters, date_column="business_date", channel_column="channel")

if reviews_f.empty:
    st.info("No reviews in the selected filters.")
    st.stop()

kpi_row(
    {
        "Avg rating": f"{reviews_f['rating'].mean():.2f} / 5",
        "Reviews": format_number(len(reviews_f)),
        "Low ratings (≤2)": format_pct((reviews_f["rating"] <= 2).mean()),
        "Response required": format_pct(reviews_f["is_response_required"].mean()),
    }
)

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Rating trend")
    trend = reviews_f.groupby("business_date", as_index=False)["rating"].mean()
    fig = px.line(trend, x="business_date", y="rating")
    fig.update_yaxes(range=[1, 5])
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

with col2:
    st.subheader("Rating distribution")
    counts = reviews_f["rating"].value_counts().sort_index().reset_index()
    counts.columns = ["rating", "count"]
    fig = px.bar(counts, x="rating", y="count", color_discrete_sequence=CATEGORICAL)
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    st.subheader("Complaint categories")
    complaints = reviews_f["complaint_category"].dropna().value_counts().reset_index()
    complaints.columns = ["complaint_category", "count"]
    if complaints.empty:
        st.info("No complaints recorded in the selected filters.")
    else:
        fig = px.bar(
            complaints,
            x="complaint_category",
            y="count",
            color="complaint_category",
            color_discrete_sequence=CATEGORICAL,
        )
        st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

with col4:
    st.subheader("Rating by channel")
    by_channel = reviews_f.groupby("channel", as_index=False)["rating"].mean()
    fig = px.bar(
        by_channel, x="channel", y="rating", color="channel", color_discrete_sequence=CATEGORICAL
    )
    fig.update_yaxes(range=[1, 5])
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

col5, col6 = st.columns(2)

with col5:
    st.subheader("Rating by preparation-time band")
    band_order = ["Under 15 min", "15-25 min", "25-35 min", "Over 35 min"]
    by_band = reviews_f.groupby("preparation_time_band", as_index=False)["rating"].mean()
    fig = px.bar(
        by_band,
        x="preparation_time_band",
        y="rating",
        category_orders={"preparation_time_band": band_order},
        color_discrete_sequence=CATEGORICAL,
    )
    fig.update_yaxes(range=[1, 5])
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

with col6:
    st.subheader("Rating by daypart")
    by_daypart = reviews_f.groupby("daypart", as_index=False)["rating"].mean()
    fig = px.bar(
        by_daypart, x="daypart", y="rating", color="daypart", color_discrete_sequence=CATEGORICAL
    )
    fig.update_yaxes(range=[1, 5])
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

st.divider()
st.subheader("Low-rating review examples")
low_ratings = reviews_f[reviews_f["rating"] <= 2].sort_values("business_date", ascending=False)
st.dataframe(
    low_ratings[["business_date", "channel", "rating", "complaint_category", "review_text"]].head(
        20
    ),
    hide_index=True,
    use_container_width=True,
)

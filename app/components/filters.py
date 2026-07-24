"""Shared sidebar filters, formatting, and KPI-card rendering.

Every page uses these so filters/formatting look and behave the same way
across the app. Each page only asks for the filters its mart actually
supports (e.g. a channel filter is meaningless on the labour-productivity
mart, which has no channel column).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd
import streamlit as st


@dataclass
class FilterState:
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    channels: list[str] | None = None
    categories: list[str] | None = None


def render_sidebar_filters(
    df: pd.DataFrame,
    *,
    date_column: str | None = None,
    channel_column: str | None = None,
    category_column: str | None = None,
    key_prefix: str = "",
) -> FilterState:
    filters = FilterState()

    if date_column and date_column in df.columns and not df.empty:
        min_date = pd.Timestamp(df[date_column].min()).date()
        max_date = pd.Timestamp(df[date_column].max()).date()
        selected = st.sidebar.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key=f"{key_prefix}_date",
        )
        if isinstance(selected, tuple) and len(selected) == 2:
            filters.start_date, filters.end_date = selected
        elif isinstance(selected, tuple) and len(selected) == 1:
            filters.start_date = filters.end_date = selected[0]
        else:
            filters.start_date = filters.end_date = selected

    if channel_column and channel_column in df.columns:
        options = sorted(df[channel_column].dropna().unique())
        filters.channels = st.sidebar.multiselect(
            "Channel", options, default=options, key=f"{key_prefix}_channel"
        )

    if category_column and category_column in df.columns:
        options = sorted(df[category_column].dropna().unique())
        filters.categories = st.sidebar.multiselect(
            "Category", options, default=options, key=f"{key_prefix}_category"
        )

    return filters


def apply_filters(
    df: pd.DataFrame,
    filters: FilterState,
    *,
    date_column: str | None = None,
    channel_column: str | None = None,
    category_column: str | None = None,
) -> pd.DataFrame:
    filtered = df

    if date_column and filters.start_date and filters.end_date:
        start, end = pd.Timestamp(filters.start_date), pd.Timestamp(filters.end_date)
        filtered = filtered[(filtered[date_column] >= start) & (filtered[date_column] <= end)]

    if channel_column and filters.channels is not None:
        filtered = filtered[filtered[channel_column].isin(filters.channels)]

    if category_column and filters.categories is not None:
        filtered = filtered[filtered[category_column].isin(filters.categories)]

    return filtered


def format_currency(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"${value:,.0f}"


def format_number(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.0f}"


def format_pct(value: float | None, *, already_fraction: bool = True) -> str:
    if value is None or pd.isna(value):
        return "—"
    scaled = value * 100 if already_fraction else value
    return f"{scaled:,.1f}%"


def format_minutes(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.1f} min"


def kpi_row(values: dict[str, str]) -> None:
    columns = st.columns(len(values))
    for column, (label, value) in zip(columns, values.items(), strict=True):
        column.metric(label, value)

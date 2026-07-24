"""Cached DuckDB access for the Streamlit app.

The app reads the dbt-built warehouse read-only. Most pages read a single
mart via `load_mart`; a handful of drill-down features need finer grain
than any mart carries (per-item-per-hour, per-item-per-channel, an
hourly-by-weekday heatmap) and query `main`/`intermediate` schema tables
directly instead — still dbt-built DuckDB tables, never the raw CSVs.
"""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from restaurant_ops.config import DATABASE_PATH

MART_NAMES = frozenset(
    {
        "mart_daily_performance",
        "mart_menu_engineering",
        "mart_channel_profitability",
        "mart_labour_productivity",
        "mart_service_quality",
        "mart_inventory_risk",
        "mart_review_analysis",
    }
)


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DATABASE_PATH), read_only=True)


@st.cache_data
def load_mart(name: str) -> pd.DataFrame:
    if name not in MART_NAMES:
        raise ValueError(f"Unknown mart: {name}")
    return get_connection().execute(f"SELECT * FROM marts.{name}").fetchdf()  # noqa: S608


@st.cache_data
def item_demand_by_hour(menu_item_id: str) -> pd.DataFrame:
    query = """
        select
            date_part('hour', fo.order_timestamp) as order_hour,
            count(*) as order_count,
            sum(foi.quantity) as quantity
        from main.fact_order_items foi
        join main.fact_orders fo using (order_id)
        where foi.menu_item_id = ?
        group by 1
        order by 1
    """
    return get_connection().execute(query, [menu_item_id]).fetchdf()


@st.cache_data
def item_demand_by_temperature(menu_item_id: str) -> pd.DataFrame:
    query = """
        select
            case
                when fo.temperature_c < 15 then '1. Cold (<15°C)'
                when fo.temperature_c < 25 then '2. Mild (15-25°C)'
                else '3. Hot (>25°C)'
            end as temperature_band,
            count(*) as order_count,
            sum(foi.quantity) as quantity
        from main.fact_order_items foi
        join main.fact_orders fo using (order_id)
        where foi.menu_item_id = ?
        group by 1
        order by 1
    """
    df = get_connection().execute(query, [menu_item_id]).fetchdf()
    df["temperature_band"] = df["temperature_band"].str.slice(3)
    return df


@st.cache_data
def item_channel_distribution(menu_item_id: str) -> pd.DataFrame:
    query = """
        select
            channel,
            count(*) as order_count,
            sum(quantity) as quantity,
            sum(line_total) as revenue
        from main.fact_order_items
        where menu_item_id = ?
        group by 1
        order by 2 desc
    """
    return get_connection().execute(query, [menu_item_id]).fetchdf()


@st.cache_data
def hourly_heatmap_by_weekday() -> pd.DataFrame:
    query = """
        select
            dd.day_name,
            ihd.order_hour,
            sum(ihd.order_count) as order_count,
            avg(ihd.avg_preparation_minutes) as avg_preparation_minutes
        from intermediate.int_hourly_demand ihd
        join main.dim_date dd on ihd.business_date = dd.business_date
        group by 1, 2
    """
    return get_connection().execute(query).fetchdf()


@st.cache_data
def prep_time_vs_promised_by_daypart() -> pd.DataFrame:
    query = """
        select
            dd.day_name,
            fo.daypart,
            count(*) as order_count,
            avg(fo.preparation_minutes) as avg_preparation_minutes,
            avg(fo.promised_minutes) as avg_promised_minutes
        from main.fact_orders fo
        join main.dim_date dd on fo.business_date = dd.business_date
        group by 1, 2
    """
    return get_connection().execute(query).fetchdf()

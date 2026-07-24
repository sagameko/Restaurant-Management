"""Feature engineering for the daily order-volume forecast.

Builds a tidy, model-ready frame from `mart_daily_performance` — one row
per business date, sorted chronologically, with the lag/rolling features
every candidate model in `models.py` draws from. Pure function, no I/O,
so it's directly unit-testable against a small hand-built frame.
"""

from __future__ import annotations

import pandas as pd

RAW_INPUT_COLUMNS = [
    "business_date",
    "day_name",
    "is_weekend",
    "is_public_holiday",
    "is_city_event",
    "promotion_name",
    "temperature_c",
    "rain_mm",
    "order_count",
]

FEATURE_FRAME_COLUMNS = [
    "business_date",
    "day_name",
    "month",
    "is_weekend",
    "is_public_holiday",
    "is_city_event",
    "has_promotion",
    "temperature_c",
    "rain_mm",
    "previous_day_orders",
    "previous_week_orders",
    "rolling_7day_avg",
    "order_count",
]


def build_feature_frame(daily: pd.DataFrame) -> pd.DataFrame:
    """Turn daily performance rows into a model-ready feature frame.

    `rolling_7day_avg` is the mean of the 7 days *before* the target day
    (shifted by 1 first) so the target day's own order count never leaks
    into its own feature. Rows without a full 7-day lag history (the
    first 7 calendar days) are dropped — there's no meaningful forecast
    input for them anyway.
    """
    df = daily[RAW_INPUT_COLUMNS].copy()
    df["business_date"] = pd.to_datetime(df["business_date"])
    df = df.sort_values("business_date").reset_index(drop=True)

    df["month"] = df["business_date"].dt.month
    df["has_promotion"] = df["promotion_name"].notna()
    df["previous_day_orders"] = df["order_count"].shift(1)
    df["previous_week_orders"] = df["order_count"].shift(7)
    df["rolling_7day_avg"] = df["order_count"].shift(1).rolling(window=7, min_periods=7).mean()

    df = df.dropna(subset=["previous_week_orders", "rolling_7day_avg"]).reset_index(drop=True)
    return df[FEATURE_FRAME_COLUMNS]

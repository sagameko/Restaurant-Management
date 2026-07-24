"""Recursive multi-day-ahead forecasting beyond the historical dataset.

The historical dataset ends on a fixed date, so the days being forecast
have no real weather/calendar data yet. `generate_daily_context` (the
same deterministic generator used to build the original synthetic
dataset — public holidays computed by rule, promotions by weekday,
weather from the seeded model) produces those features instead. Lag
features for the days furthest out recursively depend on this function's
own prior predictions, not real data — expected, and how any real
multi-step forecast works, not a bug.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from restaurant_ops.forecasting.features import RAW_INPUT_COLUMNS, build_feature_frame
from restaurant_ops.generation.weather import generate_daily_context

_CONTEXT_COLUMN_RENAME = {
    "weekend_flag": "is_weekend",
    "public_holiday_flag": "is_public_holiday",
    "city_event_flag": "is_city_event",
}


def generate_future_context(
    last_date: date, business_rules: dict, seed: int, n_days: int = 7
) -> pd.DataFrame:
    """Synthetic weather/calendar features for the `n_days` after `last_date`."""
    rng = np.random.default_rng(seed)
    raw = generate_daily_context(last_date + timedelta(days=1), n_days, business_rules, rng)
    return raw.rename(columns=_CONTEXT_COLUMN_RENAME)


def forecast_next_days(
    daily: pd.DataFrame, model, business_rules: dict, seed: int, n_days: int = 7
) -> pd.DataFrame:
    """Forecast `n_days` beyond `daily`'s last date using a fitted `model`.

    `daily` must have the same columns as `mart_daily_performance`
    (business_date, day_name, is_weekend, is_public_holiday, is_city_event,
    promotion_name, temperature_c, rain_mm, order_count). `model` must
    already be fit (typically on the full history, after being chosen as
    the best candidate via time-based holdout evaluation).
    """
    history = daily[RAW_INPUT_COLUMNS].sort_values("business_date").reset_index(drop=True)
    last_date = pd.Timestamp(history["business_date"].max()).date()
    future_context = generate_future_context(last_date, business_rules, seed, n_days)

    context_columns = [c for c in history.columns if c != "order_count"]
    predictions = []
    for _, future_row in future_context.iterrows():
        pending = {col: future_row[col] for col in context_columns}
        pending["order_count"] = np.nan
        candidate = pd.concat([history, pd.DataFrame([pending])], ignore_index=True)

        features = build_feature_frame(candidate)
        predicted_orders = float(model.predict(features.iloc[[-1]])[0])

        predictions.append(
            {
                "business_date": future_row["business_date"],
                "day_name": future_row["day_name"],
                "predicted_orders": predicted_orders,
            }
        )

        pending["order_count"] = predicted_orders
        history = pd.concat([history, pd.DataFrame([pending])], ignore_index=True)

    return pd.DataFrame(predictions)

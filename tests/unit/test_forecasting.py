"""Tests for the Phase 8 forecasting package: feature engineering,
time-based validation, the four candidate models, and the staffing
recommendation — all against small hand-built frames, independent of the
live DuckDB warehouse."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from restaurant_ops.config import get_business_rules
from restaurant_ops.forecasting.evaluation import mae, mape, rmse, time_based_split
from restaurant_ops.forecasting.features import build_feature_frame
from restaurant_ops.forecasting.future import forecast_next_days, generate_future_context
from restaurant_ops.forecasting.models import (
    MovingAverageModel,
    NaivePreviousWeekModel,
    SklearnForecastModel,
    build_model_registry,
    evaluate_models,
)
from restaurant_ops.forecasting.staffing import recommend_staffing


@pytest.fixture
def daily():
    # 21 days so build_feature_frame (which needs a 7-day lag) still
    # leaves 14 usable rows to test against.
    dates = pd.date_range("2026-01-01", periods=21, freq="D")
    rng = np.random.default_rng(0)
    order_count = (100 + 5 * np.arange(21) + rng.normal(0, 1, 21)).round().astype(int)
    return pd.DataFrame(
        {
            "business_date": dates,
            "day_name": dates.day_name(),
            "is_weekend": dates.day_name().isin(["Saturday", "Sunday"]),
            "is_public_holiday": False,
            "is_city_event": False,
            "promotion_name": [None if i % 2 == 0 else "Test Promo" for i in range(21)],
            "temperature_c": 20.0,
            "rain_mm": 0.0,
            "order_count": order_count,
        }
    )


def test_build_feature_frame_drops_incomplete_lag_rows(daily):
    features = build_feature_frame(daily)
    assert len(features) == len(daily) - 7
    assert features["previous_week_orders"].notna().all()
    assert features["rolling_7day_avg"].notna().all()


def test_build_feature_frame_lag_alignment_has_no_leakage(daily):
    features = build_feature_frame(daily)
    # Row 0 of the output corresponds to day index 7 of the input (0-indexed).
    row = features.iloc[0]
    assert row["business_date"] == daily["business_date"].iloc[7]
    assert row["previous_day_orders"] == daily["order_count"].iloc[6]
    assert row["previous_week_orders"] == daily["order_count"].iloc[0]
    expected_rolling = daily["order_count"].iloc[0:7].mean()
    assert row["rolling_7day_avg"] == pytest.approx(expected_rolling)


def test_build_feature_frame_has_promotion_matches_promotion_name(daily):
    features = build_feature_frame(daily)
    reference = daily.set_index("business_date")["promotion_name"].notna()
    for _, row in features.iterrows():
        assert row["has_promotion"] == reference.loc[row["business_date"]]


def test_time_based_split_is_chronological_not_random(daily):
    features = build_feature_frame(daily)
    train, test = time_based_split(features, test_days=5)
    assert len(test) == 5
    assert len(train) == len(features) - 5
    assert train["business_date"].max() < test["business_date"].min()


def test_time_based_split_rejects_test_days_too_large(daily):
    features = build_feature_frame(daily)
    with pytest.raises(ValueError, match="test_days"):
        time_based_split(features, test_days=len(features))


def test_metrics_match_manual_calculation():
    actual = pd.Series([100.0, 110.0, 90.0])
    predicted = pd.Series([90.0, 110.0, 100.0])
    assert mae(actual, predicted) == pytest.approx((10 + 0 + 10) / 3)
    assert rmse(actual, predicted) == pytest.approx(np.sqrt((100 + 0 + 100) / 3))
    assert mape(actual, predicted) == pytest.approx((10 / 100 + 0 / 110 + 10 / 90) / 3 * 100)


def test_naive_previous_week_model_reuses_lag_feature(daily):
    features = build_feature_frame(daily)
    model = NaivePreviousWeekModel().fit(features)
    predictions = model.predict(features)
    np.testing.assert_array_equal(predictions, features["previous_week_orders"].to_numpy())


def test_moving_average_model_reuses_rolling_feature(daily):
    features = build_feature_frame(daily)
    model = MovingAverageModel().fit(features)
    predictions = model.predict(features)
    np.testing.assert_array_equal(predictions, features["rolling_7day_avg"].to_numpy())


def test_sklearn_forecast_model_fits_and_predicts_with_consistent_columns(daily):
    features = build_feature_frame(daily)
    train, test = time_based_split(features, test_days=5)
    model = SklearnForecastModel(LinearRegression()).fit(train)
    predictions = model.predict(test)
    assert len(predictions) == len(test)
    assert np.isfinite(predictions).all()


def test_build_model_registry_and_evaluate_models_returns_one_row_per_model(daily):
    features = build_feature_frame(daily)
    train, test = time_based_split(features, test_days=5)
    models = build_model_registry()
    for model in models.values():
        model.fit(train)
    scores = evaluate_models(models, test)
    assert set(scores["model"]) == set(models)
    assert (scores["mae"] >= 0).all()
    assert (scores["rmse"] >= 0).all()


def test_recommend_staffing_arithmetic():
    labour = pd.DataFrame(
        {
            "staffing_level_flag": ["Balanced", "Balanced", "Overstaffed"],
            "orders_per_kitchen_labour_hour": [2.0, 4.0, 100.0],
            "orders_per_front_of_house_labour_hour": [5.0, 5.0, 100.0],
        }
    )
    shifts = pd.DataFrame(
        {
            "department": ["Kitchen", "Kitchen", "Front of House", "Front of House"],
            "actual_hours": [5.0, 5.0, 5.0, 5.0],
            "is_absent": [False, False, False, False],
        }
    )
    result = recommend_staffing(predicted_orders=90.0, labour=labour, shifts=shifts)
    # Kitchen benchmark = median(2.0, 4.0) = 3.0 orders/hour (the Overstaffed
    # row is excluded) -> 90 / 3.0 = 30 hours -> ceil(30 / 5.0) = 6 staff.
    assert result["kitchen_hours"] == pytest.approx(30.0)
    assert result["kitchen_headcount"] == 6
    # Front of house benchmark = median(5.0, 5.0) = 5.0 -> 90 / 5.0 = 18 hours
    # -> ceil(18 / 5.0) = 4 staff.
    assert result["front_of_house_hours"] == pytest.approx(18.0)
    assert result["front_of_house_headcount"] == 4


def test_generate_future_context_continues_after_last_date():
    business_rules = get_business_rules()
    last_date = pd.Timestamp("2026-01-21").date()
    context = generate_future_context(last_date, business_rules, seed=42, n_days=7)
    assert len(context) == 7
    assert context["business_date"].min() == pd.Timestamp("2026-01-22").date()
    assert context["business_date"].max() == pd.Timestamp("2026-01-28").date()
    assert {"is_weekend", "is_public_holiday", "is_city_event"}.issubset(context.columns)


def test_generate_future_context_is_reproducible_for_same_seed():
    business_rules = get_business_rules()
    last_date = pd.Timestamp("2026-01-21").date()
    first = generate_future_context(last_date, business_rules, seed=7, n_days=7)
    second = generate_future_context(last_date, business_rules, seed=7, n_days=7)
    pd.testing.assert_frame_equal(first, second)


def test_forecast_next_days_returns_expected_dates(daily):
    business_rules = get_business_rules()
    features = build_feature_frame(daily)
    model = NaivePreviousWeekModel().fit(features)
    forecast = forecast_next_days(daily, model, business_rules, seed=42, n_days=7)

    last_date = pd.Timestamp(daily["business_date"].max())
    expected_dates = [(last_date + pd.Timedelta(days=i)).date() for i in range(1, 8)]
    assert forecast["business_date"].tolist() == expected_dates


def test_forecast_next_days_naive_model_matches_real_history_at_this_horizon(daily):
    # At a 7-day horizon, "previous week" for every forecast day still
    # falls inside the real historical data (never inside the forecast
    # itself), so the naive model's predictions should exactly match the
    # known historical order counts 7 days earlier.
    business_rules = get_business_rules()
    features = build_feature_frame(daily)
    model = NaivePreviousWeekModel().fit(features)
    forecast = forecast_next_days(daily, model, business_rules, seed=42, n_days=7)

    known = daily.set_index("business_date")["order_count"]
    for _, row in forecast.iterrows():
        seven_days_prior = pd.Timestamp(row["business_date"]) - pd.Timedelta(days=7)
        assert row["predicted_orders"] == pytest.approx(known.loc[seven_days_prior])


class _PreviousDayStubModel:
    """A minimal model whose prediction is just yesterday's order count —
    used to prove `forecast_next_days` feeds its own predictions back in
    as lag features for later days, rather than leaving them NaN/stale."""

    def fit(self, train):
        return self

    def predict(self, df):
        return df["previous_day_orders"].to_numpy(dtype=float)


def test_forecast_next_days_feeds_predictions_back_in_recursively(daily):
    business_rules = get_business_rules()
    forecast = forecast_next_days(daily, _PreviousDayStubModel(), business_rules, seed=42, n_days=3)

    # Day 1's "previous day" is real history; days 2 and 3 can only be
    # using each prior day's *prediction*, since that data doesn't
    # otherwise exist yet.
    assert forecast.iloc[0]["predicted_orders"] == pytest.approx(daily["order_count"].iloc[-1])
    assert forecast.iloc[1]["predicted_orders"] == pytest.approx(
        forecast.iloc[0]["predicted_orders"]
    )
    assert forecast.iloc[2]["predicted_orders"] == pytest.approx(
        forecast.iloc[1]["predicted_orders"]
    )


def test_recommend_staffing_ignores_absent_shifts_when_averaging_length():
    labour = pd.DataFrame(
        {
            "staffing_level_flag": ["Balanced"],
            "orders_per_kitchen_labour_hour": [2.0],
            "orders_per_front_of_house_labour_hour": [2.0],
        }
    )
    shifts = pd.DataFrame(
        {
            "department": ["Kitchen", "Kitchen", "Front of House"],
            "actual_hours": [5.0, 0.0, 5.0],
            "is_absent": [False, True, False],
        }
    )
    result = recommend_staffing(predicted_orders=10.0, labour=labour, shifts=shifts)
    # Kitchen average shift length should be 5.0 (the absent 0-hour row is
    # excluded), not (5.0 + 0.0) / 2 = 2.5.
    assert result["kitchen_hours"] == pytest.approx(5.0)
    assert result["kitchen_headcount"] == 1

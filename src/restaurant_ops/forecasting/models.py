"""Candidate daily order-volume forecast models.

Four candidates, all sharing a `fit(train).predict(df)` interface so the
Streamlit page and the evaluation loop can treat them uniformly: a naive
previous-week baseline, a 7-day moving average, linear regression, and a
random forest. The spec only requires "naive, moving average, and linear
regression or tree-based" — both regression candidates are included
since scikit-learn makes the second one nearly free and it gives a more
useful comparison.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

from restaurant_ops.forecasting.evaluation import mae, mape, rmse

NUMERIC_FEATURE_COLUMNS = [
    "is_weekend",
    "is_public_holiday",
    "is_city_event",
    "has_promotion",
    "temperature_c",
    "rain_mm",
    "previous_day_orders",
    "previous_week_orders",
    "rolling_7day_avg",
]
CATEGORICAL_FEATURE_COLUMNS = ["day_name", "month"]


def _design_matrix(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    numeric = df[NUMERIC_FEATURE_COLUMNS].astype(float).reset_index(drop=True)
    categorical = pd.get_dummies(
        df[CATEGORICAL_FEATURE_COLUMNS].reset_index(drop=True), columns=CATEGORICAL_FEATURE_COLUMNS
    )
    encoded = pd.concat([numeric, categorical], axis=1)
    if columns is not None:
        encoded = encoded.reindex(columns=columns, fill_value=0)
    return encoded


class NaivePreviousWeekModel:
    """predicted(day) = actual order count exactly 7 days earlier."""

    def fit(self, train: pd.DataFrame) -> NaivePreviousWeekModel:
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return df["previous_week_orders"].to_numpy(dtype=float)


class MovingAverageModel:
    """predicted(day) = mean order count over the prior 7 days."""

    def fit(self, train: pd.DataFrame) -> MovingAverageModel:
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return df["rolling_7day_avg"].to_numpy(dtype=float)


class SklearnForecastModel:
    """Shared fit/predict scaffolding for the two scikit-learn candidates.

    Dummy columns are fixed at fit time and reused at predict time
    (`reindex(..., fill_value=0)`) so a category missing from a single
    future row being forecast recursively doesn't shift the feature
    matrix's columns out from under the fitted estimator.
    """

    def __init__(self, estimator) -> None:
        self._estimator = estimator
        self._columns: list[str] | None = None

    def fit(self, train: pd.DataFrame) -> SklearnForecastModel:
        design = _design_matrix(train)
        self._columns = list(design.columns)
        self._estimator.fit(design, train["order_count"])
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        design = _design_matrix(df, columns=self._columns)
        return self._estimator.predict(design)


def build_model_registry() -> dict[str, object]:
    return {
        "Naive (previous week)": NaivePreviousWeekModel(),
        "Moving average (7-day)": MovingAverageModel(),
        "Linear regression": SklearnForecastModel(LinearRegression()),
        "Random forest": SklearnForecastModel(
            RandomForestRegressor(n_estimators=200, random_state=42)
        ),
    }


def evaluate_models(models: dict[str, object], test: pd.DataFrame) -> pd.DataFrame:
    """Score every fitted model in `models` against `test`. Returns one row per model."""
    actual = test["order_count"]
    rows = []
    for name, model in models.items():
        predicted = model.predict(test)
        rows.append(
            {
                "model": name,
                "mae": mae(actual, predicted),
                "rmse": rmse(actual, predicted),
                "mape": mape(actual, predicted),
            }
        )
    return pd.DataFrame(rows)

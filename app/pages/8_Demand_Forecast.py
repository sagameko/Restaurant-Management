"""Page 8: Demand Forecast."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from components.charts import CATEGORICAL, style_fig  # noqa: E402
from components.database import load_employee_shifts, load_mart  # noqa: E402
from components.filters import format_number, kpi_row  # noqa: E402

from restaurant_ops.config import get_business_rules, get_simulation_settings  # noqa: E402
from restaurant_ops.forecasting.evaluation import time_based_split  # noqa: E402
from restaurant_ops.forecasting.features import build_feature_frame  # noqa: E402
from restaurant_ops.forecasting.future import forecast_next_days  # noqa: E402
from restaurant_ops.forecasting.models import build_model_registry, evaluate_models  # noqa: E402
from restaurant_ops.forecasting.staffing import recommend_staffing  # noqa: E402

st.set_page_config(page_title="Demand Forecast", page_icon="🍜", layout="wide")
st.title("Demand Forecast")

st.warning(
    "This forecast is trained entirely on **synthetic historical data** "
    "from this project's data generator, not real order history — treat "
    "it as a demonstration of the forecasting approach, not a real "
    "demand prediction.",
    icon="⚠️",
)

TEST_DAYS = 60
FORECAST_DAYS = 7


@st.cache_data
def run_forecast_pipeline():
    daily = load_mart("mart_daily_performance")
    labour = load_mart("mart_labour_productivity")
    shifts = load_employee_shifts()

    features = build_feature_frame(daily)
    train, test = time_based_split(features, test_days=TEST_DAYS)

    models = build_model_registry()
    for model in models.values():
        model.fit(train)
    scores = evaluate_models(models, test).sort_values("mae").reset_index(drop=True)
    predictions = {name: model.predict(test) for name, model in models.items()}

    best_name = scores.iloc[0]["model"]
    business_rules = get_business_rules()
    seed = get_simulation_settings().simulation.random_seed

    best_model = models[best_name].fit(features)  # refit on all available history
    forecast = forecast_next_days(
        daily, best_model, business_rules, seed=seed, n_days=FORECAST_DAYS
    )
    forecast["staffing"] = forecast["predicted_orders"].apply(
        lambda orders: recommend_staffing(orders, labour, shifts)
    )

    return {
        "test": test,
        "scores": scores,
        "predictions": predictions,
        "best_name": best_name,
        "forecast": forecast,
    }


result = run_forecast_pipeline()
test = result["test"]
scores = result["scores"]
predictions = result["predictions"]
best_name = result["best_name"]
forecast = result["forecast"]

st.subheader("Model comparison")
st.caption(
    f"Trained on all days before the last {TEST_DAYS}, evaluated on those "
    f"{TEST_DAYS} held-out days — a chronological split, never a random one."
)
display_scores = scores.rename(
    columns={"model": "Model", "mae": "MAE", "rmse": "RMSE", "mape": "MAPE (%)"}
)
display_scores["MAE"] = display_scores["MAE"].map(lambda x: f"{x:.1f}")
display_scores["RMSE"] = display_scores["RMSE"].map(lambda x: f"{x:.1f}")
display_scores["MAPE (%)"] = display_scores["MAPE (%)"].map(lambda x: f"{x:.1f}%")
st.dataframe(display_scores, hide_index=True, use_container_width=True)
st.caption(f"Best model on this holdout: **{best_name}**, used for the forecast below.")

st.divider()

st.subheader("Actual vs. predicted demand (holdout period)")
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=test["business_date"],
        y=test["order_count"],
        name="Actual",
        line={"color": "#0b0b0b", "width": 3},
    )
)
for i, (name, preds) in enumerate(predictions.items()):
    fig.add_trace(
        go.Scatter(
            x=test["business_date"],
            y=preds,
            name=name,
            line={"color": CATEGORICAL[i % len(CATEGORICAL)], "dash": "dot"},
        )
    )
st.plotly_chart(style_fig(fig), use_container_width=True)

st.divider()

st.subheader(f"Upcoming {FORECAST_DAYS}-day forecast")
fig = px.bar(
    forecast,
    x="business_date",
    y="predicted_orders",
    color_discrete_sequence=CATEGORICAL,
    labels={"business_date": "Date", "predicted_orders": "Predicted orders"},
)
st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)
kpi_row(
    {
        "Forecast total": format_number(forecast["predicted_orders"].sum()),
        "Forecast daily avg": format_number(forecast["predicted_orders"].mean()),
    }
)

st.divider()

st.subheader("Recommended staffing")
staffing_table = pd.DataFrame(
    {
        "Date": forecast["business_date"],
        "Day": forecast["day_name"],
        "Predicted orders": forecast["predicted_orders"].round(0).astype(int),
        "Kitchen staff": [s["kitchen_headcount"] for s in forecast["staffing"]],
        "Front of House staff": [s["front_of_house_headcount"] for s in forecast["staffing"]],
    }
)
st.dataframe(staffing_table, hide_index=True, use_container_width=True)
st.caption(
    "Headcount = predicted orders ÷ the observed orders-per-labour-hour "
    "benchmark on 'Balanced' historical days, ÷ average real shift length."
)

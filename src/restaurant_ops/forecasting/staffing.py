"""Translate a predicted order count into a recommended headcount.

Entirely driven by observed warehouse data — no new hardcoded
assumptions: the orders-per-labour-hour benchmark comes from
`mart_labour_productivity`'s own `Balanced` days (not an over/understaffed
outlier), and the average shift length comes from real, actually-worked
shifts in `fact_employee_shifts`.
"""

from __future__ import annotations

import math

import pandas as pd


def recommend_staffing(predicted_orders: float, labour: pd.DataFrame, shifts: pd.DataFrame) -> dict:
    balanced = labour[labour["staffing_level_flag"] == "Balanced"]
    kitchen_benchmark = balanced["orders_per_kitchen_labour_hour"].median()
    front_of_house_benchmark = balanced["orders_per_front_of_house_labour_hour"].median()

    worked_shifts = shifts[~shifts["is_absent"]]
    avg_shift_hours = worked_shifts.groupby("department")["actual_hours"].mean()
    kitchen_shift_hours = avg_shift_hours["Kitchen"]
    front_of_house_shift_hours = avg_shift_hours["Front of House"]

    kitchen_hours = predicted_orders / kitchen_benchmark
    front_of_house_hours = predicted_orders / front_of_house_benchmark

    return {
        "kitchen_hours": kitchen_hours,
        "kitchen_headcount": math.ceil(kitchen_hours / kitchen_shift_hours),
        "front_of_house_hours": front_of_house_hours,
        "front_of_house_headcount": math.ceil(front_of_house_hours / front_of_house_shift_hours),
    }

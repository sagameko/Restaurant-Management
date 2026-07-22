"""Employee shift generation.

Schedules real employees against the target roster in
`config/business_rules.yaml: kitchen_capacity.staff_roster`, including
random absences — which is what lets kitchen staffing actually vary
day to day instead of being a fixed constant (spec: "preparation time
should depend on ... employee absence").

Alongside the persisted shift table (matching the spec's exact required
`Employee shifts` columns, which don't include a daypart column), this
returns a `(business_date, daypart) -> (kitchen_count, front_of_house_count)`
lookup of *effective* (non-absent) staff counts for
`restaurant_ops.generation.orders` to compute `kitchen_load_ratio` from.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd

from restaurant_ops.ingestion.schemas import Employee

_DEPARTMENT_ROSTER_KEY = {"Kitchen": "kitchen", "Front of House": "front_of_house"}


def _shift_window(
    business_date: date, daypart_cfg: dict, staffing_cfg: dict
) -> tuple[datetime, datetime]:
    day_start = datetime.combine(business_date, time())
    shift_start = day_start + timedelta(
        hours=daypart_cfg["start_hour"] - staffing_cfg["shift_buffer_before_hours"]
    )
    shift_end = day_start + timedelta(
        hours=daypart_cfg["end_hour"] + staffing_cfg["shift_buffer_after_hours"]
    )
    return shift_start, shift_end


def generate_shifts(
    daily_context: pd.DataFrame,
    employees: list[Employee],
    business_rules: dict,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, dict[tuple[date, str], tuple[int, int]]]:
    """Generate the Employee shifts table and an effective-staffing lookup."""
    staffing_cfg = business_rules["staffing"]
    dayparts_cfg = business_rules["dayparts"]
    staff_roster = business_rules["kitchen_capacity"]["staff_roster"]

    employees_by_department: dict[str, list[Employee]] = {"Kitchen": [], "Front of House": []}
    for employee in employees:
        if employee.active:
            employees_by_department[employee.department].append(employee)

    shift_rows: list[dict] = []
    staffing_lookup: dict[tuple[date, str], tuple[int, int]] = {}
    shift_counter = 0

    for _, context_row in daily_context.iterrows():
        business_date = context_row["business_date"]
        roster_category = "weekend" if context_row["weekend_flag"] else "weekday"

        for daypart in ("lunch", "dinner"):
            roster_target = staff_roster[roster_category][daypart]
            shift_start, shift_end = _shift_window(
                business_date, dayparts_cfg[daypart], staffing_cfg
            )
            scheduled_hours = (shift_end - shift_start).total_seconds() / 3600
            break_minutes = (
                staffing_cfg["break_minutes"]
                if scheduled_hours > staffing_cfg["break_minutes_threshold_hours"]
                else 0
            )

            effective_counts = {"Kitchen": 0, "Front of House": 0}
            for department, target_count in (
                ("Kitchen", roster_target["kitchen"]),
                ("Front of House", roster_target["front_of_house"]),
            ):
                pool = employees_by_department[department]
                headcount = min(target_count, len(pool))
                chosen_idx = rng.choice(len(pool), size=headcount, replace=False)

                for idx in chosen_idx:
                    employee = pool[int(idx)]
                    absence_flag = rng.random() < staffing_cfg["absence_probability"]
                    if absence_flag:
                        actual_hours = 0.0
                    else:
                        actual_hours = max(
                            0.0,
                            scheduled_hours
                            - break_minutes / 60
                            + rng.normal(0, staffing_cfg["actual_hours_variance_std_hours"]),
                        )
                        effective_counts[department] += 1
                    # Round before costing so labour_cost reconciles exactly
                    # against the stored actual_hours, not the unrounded
                    # internal value.
                    actual_hours = round(actual_hours, 2)

                    shift_counter += 1
                    shift_rows.append(
                        {
                            "shift_id": f"SFT{shift_counter:06d}",
                            "employee_id": employee.employee_id,
                            "business_date": business_date,
                            "role": employee.role,
                            "shift_start": shift_start,
                            "shift_end": shift_end,
                            "break_minutes": break_minutes,
                            "scheduled_hours": round(scheduled_hours, 2),
                            "actual_hours": actual_hours,
                            "absence_flag": absence_flag,
                            "hourly_rate": employee.hourly_rate,
                            "labour_cost": round(actual_hours * employee.hourly_rate, 2),
                        }
                    )

            staffing_lookup[(business_date, daypart)] = (
                max(1, effective_counts["Kitchen"]),
                max(1, effective_counts["Front of House"]),
            )

    return pd.DataFrame(shift_rows), staffing_lookup

"""Tests for employee shift generation."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from pandas.testing import assert_frame_equal

from restaurant_ops.config import get_business_rules
from restaurant_ops.generation.staffing import generate_shifts
from restaurant_ops.generation.weather import generate_daily_context
from restaurant_ops.ingestion.loader import load_employees
from restaurant_ops.validation.rules import validate_shifts

_START_DATE = date(2025, 7, 1)
_DAYS = 60
_SEED = 42


def _generate(seed: int = _SEED):
    business_rules = get_business_rules()
    employees = load_employees()
    rng = np.random.default_rng(seed)
    daily_context = generate_daily_context(_START_DATE, _DAYS, business_rules, rng)
    return generate_shifts(daily_context, employees, business_rules, rng)


@pytest.fixture(scope="module")
def generated():
    return _generate()


@pytest.fixture(scope="module")
def employee_ids():
    return {e.employee_id for e in load_employees()}


def test_same_seed_produces_identical_shifts():
    shifts_a, _ = _generate(seed=7)
    shifts_b, _ = _generate(seed=7)
    assert_frame_equal(shifts_a, shifts_b)


def test_no_validation_errors(generated, employee_ids):
    shifts, _ = generated
    assert validate_shifts(shifts, employee_ids) == []


def test_shift_end_after_shift_start(generated):
    shifts, _ = generated
    assert (shifts["shift_end"] > shifts["shift_start"]).all()


def test_absence_rate_close_to_configured_probability(generated):
    shifts, _ = generated
    business_rules = get_business_rules()
    configured = business_rules["staffing"]["absence_probability"]
    observed = shifts["absence_flag"].mean()
    assert abs(observed - configured) < 0.02


def test_absent_shifts_have_zero_actual_hours_and_labour_cost(generated):
    shifts, _ = generated
    absent = shifts[shifts["absence_flag"]]
    assert (absent["actual_hours"] == 0).all()
    assert (absent["labour_cost"] == 0).all()


def test_present_shifts_have_positive_actual_hours(generated):
    shifts, _ = generated
    present = shifts[~shifts["absence_flag"]]
    assert (present["actual_hours"] > 0).all()


def test_labour_cost_equals_actual_hours_times_hourly_rate(generated):
    shifts, _ = generated
    expected = (shifts["actual_hours"] * shifts["hourly_rate"]).round(2)
    # 0.02 tolerance: Python's round() and pandas' .round() can land on
    # opposite sides of an exact-half cent (e.g. 4.23 x 25.5 = 107.865),
    # a floating-point boundary artifact, not a real reconciliation gap.
    assert (shifts["labour_cost"] - expected).abs().lt(0.02).all()


def test_long_shifts_get_a_break_short_shifts_do_not(generated):
    shifts, _ = generated
    business_rules = get_business_rules()
    threshold = business_rules["staffing"]["break_minutes_threshold_hours"]
    long_shifts = shifts[shifts["scheduled_hours"] > threshold]
    short_shifts = shifts[shifts["scheduled_hours"] <= threshold]
    assert (long_shifts["break_minutes"] > 0).all()
    assert (short_shifts["break_minutes"] == 0).all()


def test_effective_staffing_lookup_never_exceeds_roster_target(generated):
    _, staffing_lookup = generated
    business_rules = get_business_rules()
    roster = business_rules["kitchen_capacity"]["staff_roster"]

    daily_context = generate_daily_context(
        _START_DATE, _DAYS, business_rules, np.random.default_rng(_SEED)
    )
    weekend_dates = set(daily_context.loc[daily_context["weekend_flag"], "business_date"])

    for (business_date, daypart), (kitchen_count, foh_count) in staffing_lookup.items():
        category = "weekend" if business_date in weekend_dates else "weekday"
        target = roster[category][daypart]
        assert kitchen_count <= target["kitchen"]
        assert foh_count <= target["front_of_house"]


def test_effective_staffing_sometimes_falls_short_of_target_due_to_absence(generated):
    """With a >0 absence probability across many shifts, at least some
    (business_date, daypart) slots should come in under the roster target —
    otherwise absence isn't actually affecting kitchen_load_ratio at all."""
    _, staffing_lookup = generated
    business_rules = get_business_rules()
    roster = business_rules["kitchen_capacity"]["staff_roster"]

    daily_context = generate_daily_context(
        _START_DATE, _DAYS, business_rules, np.random.default_rng(_SEED)
    )
    weekend_dates = set(daily_context.loc[daily_context["weekend_flag"], "business_date"])

    shortfalls = 0
    for (business_date, daypart), (kitchen_count, foh_count) in staffing_lookup.items():
        category = "weekend" if business_date in weekend_dates else "weekday"
        target = roster[category][daypart]
        if kitchen_count < target["kitchen"] or foh_count < target["front_of_house"]:
            shortfalls += 1
    assert shortfalls > 0

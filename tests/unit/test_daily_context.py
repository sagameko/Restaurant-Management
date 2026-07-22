"""Tests for calendar/weather (daily context) generation."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from pandas.testing import assert_frame_equal

from restaurant_ops.config import get_business_rules
from restaurant_ops.generation.weather import generate_daily_context, victorian_public_holidays


def test_victorian_public_holidays_known_fixed_dates():
    holidays = victorian_public_holidays(2026)
    assert holidays[date(2026, 1, 1)] == "New Year's Day"
    assert holidays[date(2026, 1, 26)] == "Australia Day"
    assert holidays[date(2026, 4, 25)] == "ANZAC Day"
    assert holidays[date(2026, 12, 25)] == "Christmas Day"
    assert holidays[date(2026, 12, 26)] == "Boxing Day"


def test_victorian_public_holidays_computed_dates_fall_on_expected_weekdays():
    holidays = victorian_public_holidays(2026)
    holiday_by_name = {name: d for d, name in holidays.items()}

    # Labour Day and King's Birthday are always Mondays; Melbourne Cup is
    # always a Tuesday; Easter Monday is always the day after Good Friday.
    assert holiday_by_name["Labour Day"].weekday() == 0
    assert holiday_by_name["King's Birthday"].weekday() == 0
    assert holiday_by_name["Melbourne Cup Day"].weekday() == 1
    assert holiday_by_name["Easter Monday"] == holiday_by_name["Good Friday"] + timedelta(days=3)


def test_generate_daily_context_covers_requested_range():
    rng = np.random.default_rng(42)
    business_rules = get_business_rules()
    df = generate_daily_context(date(2025, 7, 1), 30, business_rules, rng)

    assert len(df) == 30
    assert df["business_date"].iloc[0] == date(2025, 7, 1)
    assert df["business_date"].iloc[-1] == date(2025, 7, 30)
    assert df["rain_mm"].ge(0).all()
    assert df["weekend_flag"].dtype == bool


def test_generate_daily_context_is_reproducible():
    business_rules = get_business_rules()
    df1 = generate_daily_context(date(2025, 7, 1), 60, business_rules, np.random.default_rng(42))
    df2 = generate_daily_context(date(2025, 7, 1), 60, business_rules, np.random.default_rng(42))
    assert_frame_equal(df1, df2)

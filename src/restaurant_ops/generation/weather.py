"""Daily-context generation: the calendar/weather table every other
generator depends on for demand modelling (`business_date`, `day_name`,
`temperature_c`, `rain_mm`, `weekend_flag`, `public_holiday_flag`,
`city_event_flag`, `promotion_name`).

Weather is a synthetic seasonal model, not historical data — see
`docs/limitations.md`. Public holiday dates are computed from the actual
Victorian public holiday rules (not hardcoded per-year), since those are
public calendar facts, not confidential or synthetic data. City events
are fictional, per the project's data policy.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

_WEEKDAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th occurrence of `weekday` (0=Monday..6=Sunday) in a month."""
    first_of_month = date(year, month, 1)
    offset = (weekday - first_of_month.weekday()) % 7
    return first_of_month + timedelta(days=offset + 7 * (n - 1))


def _easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm (Meeus/Jones/Butcher)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month = (h + ll - 7 * m + 114) // 31
    day = ((h + ll - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def victorian_public_holidays(year: int) -> dict[date, str]:
    """Victoria, Australia public holidays for a calendar year."""
    easter_sunday = _easter_sunday(year)
    holidays = {
        date(year, 1, 1): "New Year's Day",
        date(year, 1, 26): "Australia Day",
        _nth_weekday_of_month(year, 3, 0, 2): "Labour Day",
        easter_sunday - timedelta(days=2): "Good Friday",
        easter_sunday + timedelta(days=1): "Easter Monday",
        date(year, 4, 25): "ANZAC Day",
        _nth_weekday_of_month(year, 6, 0, 2): "King's Birthday",
        _nth_weekday_of_month(year, 11, 1, 1): "Melbourne Cup Day",
        date(year, 12, 25): "Christmas Day",
        date(year, 12, 26): "Boxing Day",
    }
    return holidays


def _city_event_dates(years: set[int], city_events: list[dict]) -> set[date]:
    return {date(year, event["month"], event["day"]) for year in years for event in city_events}


def _promotion_for_weekday(weekday_name: str, promotion_schedule: list[dict]) -> str | None:
    for promo in promotion_schedule:
        if promo["weekday"] == weekday_name:
            return promo["name"]
    return None


def _daily_temperature_c(day_of_year: int, weather_model: dict, rng: np.random.Generator) -> float:
    mean = weather_model["mean_temperature_c"]
    amplitude = weather_model["amplitude_c"]
    peak_day = weather_model["peak_day_of_year"]
    seasonal = amplitude * math.cos(2 * math.pi * (day_of_year - peak_day) / 365.25)
    noise = rng.normal(0, weather_model["daily_noise_std_c"])
    return round(mean + seasonal + noise, 1)


def _daily_rain_mm(month: int, weather_model: dict, rng: np.random.Generator) -> float:
    if month in weather_model["winter_months"]:
        rain_probability = weather_model["winter_rain_probability"]
    elif month in weather_model["summer_months"]:
        rain_probability = weather_model["summer_rain_probability"]
    else:
        rain_probability = weather_model["shoulder_rain_probability"]
    if rng.random() >= rain_probability:
        return 0.0
    return round(float(rng.exponential(weather_model["rain_mm_scale"])), 1)


def generate_daily_context(
    start_date: date, number_of_days: int, business_rules: dict, rng: np.random.Generator
) -> pd.DataFrame:
    """Generate one row per business date across the simulation window."""
    dates = [start_date + timedelta(days=offset) for offset in range(number_of_days)]
    years = {d.year for d in dates}
    holidays: dict[date, str] = {}
    for year in years:
        holidays.update(victorian_public_holidays(year))
    event_dates = _city_event_dates(years, business_rules["city_events"])
    promotion_schedule = business_rules["promotions"]["schedule"]
    weather_model = business_rules["weather_model"]

    rows = []
    for business_date in dates:
        weekday_index = business_date.weekday()
        weekday_name = _WEEKDAY_NAMES[weekday_index]
        rows.append(
            {
                "business_date": business_date,
                "day_name": weekday_name.capitalize(),
                "temperature_c": _daily_temperature_c(
                    business_date.timetuple().tm_yday, weather_model, rng
                ),
                "rain_mm": _daily_rain_mm(business_date.month, weather_model, rng),
                "weekend_flag": weekday_index >= 5,
                "public_holiday_flag": business_date in holidays,
                "city_event_flag": business_date in event_dates,
                "promotion_name": _promotion_for_weekday(weekday_name, promotion_schedule),
            }
        )
    return pd.DataFrame(rows)

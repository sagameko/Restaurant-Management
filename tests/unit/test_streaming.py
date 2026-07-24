"""Tests for the Phase 10 streaming package: the intraday/weekday rate
model, the Poisson-thinning event simulator, and the rolling-window
aggregator — all pure/deterministic, no real sleeping or network."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
import pytest

from restaurant_ops.config import get_business_rules
from restaurant_ops.streaming.aggregator import RollingWindowAggregator
from restaurant_ops.streaming.events import OrderEvent
from restaurant_ops.streaming.session import SessionHistory, compute_session_summary
from restaurant_ops.streaming.simulator import (
    LiveOrderSimulator,
    _intraday_intensity,
    _triangular_pdf,
    arrival_rate_per_hour,
    default_start_time,
)


@pytest.fixture
def business_rules():
    return get_business_rules()


def make_event(
    timestamp: datetime, *, channel="dine_in", item_count=2, subtotal=25.0
) -> OrderEvent:
    return OrderEvent(
        event_id="evt-1",
        timestamp=timestamp,
        channel=channel,
        daypart="lunch",
        item_count=item_count,
        subtotal=subtotal,
    )


def test_triangular_pdf_zero_outside_bounds():
    assert _triangular_pdf(10.9, 11, 12.5, 15) == 0.0
    assert _triangular_pdf(15.1, 11, 12.5, 15) == 0.0


def test_triangular_pdf_peaks_at_mode():
    values = np.linspace(11, 15, 401)
    densities = [_triangular_pdf(v, 11, 12.5, 15) for v in values]
    assert densities[np.argmax(densities)] == pytest.approx(max(densities))
    peak_index = int(np.argmin(np.abs(values - 12.5)))
    assert densities[peak_index] == pytest.approx(max(densities), rel=1e-2)


def test_intraday_intensity_integrates_to_one_over_a_day(business_rules):
    hours = np.linspace(0, 24, 24 * 60, endpoint=False)
    densities = [_intraday_intensity(h, business_rules) for h in hours]
    integral = np.trapezoid(densities, hours)
    assert integral == pytest.approx(1.0, abs=0.01)


def test_arrival_rate_is_zero_outside_service_hours(business_rules):
    closed = datetime(2026, 1, 5, 3, 0)  # Monday 3am
    assert arrival_rate_per_hour(closed, business_rules, average_daily_orders=100) == 0.0


def test_arrival_rate_is_positive_during_lunch_and_dinner(business_rules):
    lunch_peak = datetime(2026, 1, 5, 12, 30)  # Monday lunch peak
    dinner_peak = datetime(2026, 1, 5, 19, 0)  # Monday dinner peak
    assert arrival_rate_per_hour(lunch_peak, business_rules, average_daily_orders=100) > 0
    assert arrival_rate_per_hour(dinner_peak, business_rules, average_daily_orders=100) > 0


def test_arrival_rate_is_higher_on_saturday_than_monday(business_rules):
    monday_dinner = datetime(2026, 1, 5, 19, 0)
    saturday_dinner = datetime(2026, 1, 10, 19, 0)
    monday_rate = arrival_rate_per_hour(monday_dinner, business_rules, average_daily_orders=100)
    saturday_rate = arrival_rate_per_hour(saturday_dinner, business_rules, average_daily_orders=100)
    assert saturday_rate > monday_rate


def test_default_start_time_falls_inside_todays_lunch_window(business_rules):
    start = default_start_time()
    assert start.date() == datetime.now().date()
    # Guaranteed non-zero arrival rate at that exact moment, regardless
    # of what real wall-clock time the server happens to start at.
    assert arrival_rate_per_hour(start, business_rules, average_daily_orders=100) > 0


@pytest.fixture
def simulator(business_rules):
    channel_probabilities = {"dine_in": 0.4, "pickup": 0.25, "uber_eats": 0.23, "doordash": 0.12}
    return LiveOrderSimulator(
        business_rules=business_rules,
        average_daily_orders=100,
        average_item_price=15.0,
        channel_probabilities=channel_probabilities,
        rng=np.random.default_rng(42),
    )


def test_generate_events_is_deterministic_for_a_fixed_seed(business_rules):
    channel_probabilities = {"dine_in": 0.4, "pickup": 0.25, "uber_eats": 0.23, "doordash": 0.12}
    start = datetime(2026, 1, 5, 0, 0)

    def build():
        return LiveOrderSimulator(
            business_rules=business_rules,
            average_daily_orders=100,
            average_item_price=15.0,
            channel_probabilities=channel_probabilities,
            rng=np.random.default_rng(7),
        )

    first = build().generate_events(start, duration_hours=24)
    second = build().generate_events(start, duration_hours=24)
    assert [e.event_id for e in first] != [e.event_id for e in second]  # uuids differ
    assert [(e.timestamp, e.channel, e.item_count, e.subtotal) for e in first] == [
        (e.timestamp, e.channel, e.item_count, e.subtotal) for e in second
    ]


def test_generate_events_only_arrive_during_service_hours(simulator):
    start = datetime(2026, 1, 5, 0, 0)
    events = simulator.generate_events(start, duration_hours=7 * 24)
    assert len(events) > 0
    for event in events:
        hour = event.timestamp.hour + event.timestamp.minute / 60
        assert 11 <= hour < 21


def test_generate_events_count_is_in_a_plausible_range_over_a_week(simulator):
    start = datetime(2026, 1, 5, 0, 0)  # Monday
    events = simulator.generate_events(start, duration_hours=7 * 24)
    # ~100/day average across a week of weekday multipliers (0.85-1.25) -> ~700 expected.
    assert 400 < len(events) < 1100


def test_generate_events_item_counts_and_channels_are_within_configured_domain(
    simulator, business_rules
):
    start = datetime(2026, 1, 5, 0, 0)
    events = simulator.generate_events(start, duration_hours=3 * 24)
    valid_counts = set(business_rules["demand"]["items_per_order_weights"].keys())
    for event in events:
        assert event.item_count in valid_counts
        assert event.channel in {"dine_in", "pickup", "uber_eats", "doordash"}
        assert event.subtotal > 0


def test_stream_caps_real_sleep_across_the_overnight_gap(simulator):
    # Dinner closes at 21:00; the next arrival isn't until tomorrow's
    # lunch — a real gap of ~14 simulated hours. At time_scale=60 that's
    # a ~14 *real* minute wait for a single asyncio.sleep, which would
    # make a live demo look frozen rather than just quiet overnight.
    # max_real_sleep_seconds must cap that single wait, not just make
    # sleeps "shorter on average".
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    async def run() -> None:
        with patch("restaurant_ops.streaming.simulator.asyncio.sleep", fake_sleep):
            start = datetime(2026, 1, 5, 20, 55)  # 5 minutes before dinner close
            stream = simulator.stream(start_time=start, time_scale=60.0, max_real_sleep_seconds=5.0)
            for _ in range(3):
                await stream.__anext__()

    asyncio.run(run())

    assert sleep_calls, "expected at least one sleep to have been recorded"
    assert max(sleep_calls) <= 5.0


def test_rolling_window_aggregator_evicts_old_events():
    aggregator = RollingWindowAggregator(window_minutes=10)
    base = datetime(2026, 1, 5, 12, 0)
    aggregator.add(make_event(base, subtotal=10.0))
    aggregator.add(make_event(base + timedelta(minutes=10), subtotal=20.0))

    summary = aggregator.snapshot(reference_time=base + timedelta(minutes=10))
    assert summary.order_count == 2
    assert summary.total_revenue == pytest.approx(30.0)

    # Advance past the window: the first event should age out, the second
    # (still within 10 minutes of the new reference time) should not.
    later_summary = aggregator.snapshot(reference_time=base + timedelta(minutes=16))
    assert later_summary.order_count == 1
    assert later_summary.total_revenue == pytest.approx(20.0)


def test_rolling_window_aggregator_counts_by_channel():
    aggregator = RollingWindowAggregator(window_minutes=60)
    base = datetime(2026, 1, 5, 12, 0)
    aggregator.add(make_event(base, channel="dine_in"))
    aggregator.add(make_event(base + timedelta(minutes=1), channel="dine_in"))
    aggregator.add(make_event(base + timedelta(minutes=2), channel="pickup"))

    summary = aggregator.snapshot(reference_time=base + timedelta(minutes=3))
    assert summary.orders_by_channel == {"dine_in": 2, "pickup": 1}


def test_rolling_window_aggregator_recent_events_respects_limit():
    aggregator = RollingWindowAggregator(window_minutes=60)
    base = datetime(2026, 1, 5, 12, 0)
    for i in range(5):
        aggregator.add(make_event(base + timedelta(minutes=i)))

    recent = aggregator.recent_events(limit=2)
    assert len(recent) == 2
    assert recent[-1].timestamp == base + timedelta(minutes=4)


def test_session_history_caps_at_maxlen():
    history = SessionHistory(maxlen=3)
    base = datetime(2026, 1, 5, 12, 0)
    for i in range(5):
        history.add(make_event(base + timedelta(minutes=i)))

    events = history.events
    assert len(events) == 3
    # Oldest two evicted; the most recent three survive, in order.
    assert [e.timestamp for e in events] == [
        base + timedelta(minutes=2),
        base + timedelta(minutes=3),
        base + timedelta(minutes=4),
    ]


def test_compute_session_summary_totals_and_busiest_channel():
    base = datetime(2026, 1, 5, 12, 0)
    events = [
        make_event(base, channel="dine_in", subtotal=10.0),
        make_event(base + timedelta(minutes=1), channel="dine_in", subtotal=20.0),
        make_event(base + timedelta(minutes=2), channel="pickup", subtotal=15.0),
    ]

    summary = compute_session_summary(events, session_start=base)

    assert summary.total_orders == 3
    assert summary.total_revenue == pytest.approx(45.0)
    assert summary.busiest_channel == "dine_in"
    assert summary.orders_by_channel == {"dine_in": 2, "pickup": 1}
    assert summary.session_duration_minutes == pytest.approx(2.0)


def test_compute_session_summary_peak_orders_per_minute():
    base = datetime(2026, 1, 5, 12, 0)
    events = [
        make_event(base, subtotal=10.0),
        make_event(base + timedelta(seconds=30), subtotal=10.0),
        make_event(base + timedelta(minutes=1), subtotal=10.0),
    ]

    summary = compute_session_summary(events, session_start=base)

    assert summary.peak_orders_per_minute == 2


def test_compute_session_summary_handles_no_events():
    base = datetime(2026, 1, 5, 12, 0)
    summary = compute_session_summary([], session_start=base)

    assert summary.total_orders == 0
    assert summary.total_revenue == 0.0
    assert summary.busiest_channel is None
    assert summary.orders_by_channel == {}
    assert summary.peak_orders_per_minute == 0
    assert summary.session_duration_minutes == pytest.approx(0.0)

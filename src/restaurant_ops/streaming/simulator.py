"""A live, real-time order-event simulator.

Reuses the *same* weekday/daypart demand shape already encoded in
`config/business_rules.yaml` (`dayparts.*`, `demand.weekday_multipliers`,
`demand.daypart_share`, `demand.items_per_order_weights`) rather than
inventing a separate rate model — the live feed's rhythm should actually
resemble the historical dataset's, not just look busy.

Arrivals are generated as a non-homogeneous Poisson process via the
standard thinning algorithm: draw a candidate arrival from the fastest
possible rate (`lambda_max`), then accept it with probability
`actual_rate(t) / lambda_max`. This naturally produces slow/no arrivals
outside opening hours without any special-cased "is the restaurant open"
branch — the rate function is just zero there.

The pure, unit-testable core (`generate_events`) never sleeps. The thin
`stream()` wrapper adds real (optionally time-scaled) pacing on top, for
the live FastAPI app.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import numpy as np

from restaurant_ops.config import get_business_rules, get_simulation_settings
from restaurant_ops.ingestion.loader import load_menu_items
from restaurant_ops.streaming.events import Channel, Daypart, OrderEvent

_WEEKDAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def _triangular_pdf(x: float, low: float, mode: float, high: float) -> float:
    if x < low or x > high:
        return 0.0
    if x <= mode:
        return 2 * (x - low) / ((high - low) * (mode - low))
    return 2 * (high - x) / ((high - low) * (high - mode))


def _daypart_bounds(business_rules: dict, daypart: Daypart) -> tuple[float, float, float]:
    cfg = business_rules["dayparts"][daypart]
    return cfg["start_hour"], cfg["peak_hour"], cfg["end_hour"]


def _intraday_intensity(hour: float, business_rules: dict) -> float:
    """Probability density over hour-of-day (integrates to 1 across a
    full day): a mixture of the lunch and dinner triangular windows,
    weighted by their share of daily orders."""
    dinner_share = business_rules["demand"]["daypart_share"]["dinner_base"]
    lunch_share = 1 - dinner_share
    lunch = _triangular_pdf(hour, *_daypart_bounds(business_rules, "lunch"))
    dinner = _triangular_pdf(hour, *_daypart_bounds(business_rules, "dinner"))
    return lunch_share * lunch + dinner_share * dinner


def _max_intraday_intensity(business_rules: dict) -> float:
    """A safe (not necessarily tight) upper bound on `_intraday_intensity`,
    from each triangular window's own peak density (2 / width)."""
    dinner_share = business_rules["demand"]["daypart_share"]["dinner_base"]
    lunch_share = 1 - dinner_share
    lunch_start, _, lunch_end = _daypart_bounds(business_rules, "lunch")
    dinner_start, _, dinner_end = _daypart_bounds(business_rules, "dinner")
    return lunch_share * (2 / (lunch_end - lunch_start)) + dinner_share * (
        2 / (dinner_end - dinner_start)
    )


def _weekday_multiplier(business_rules: dict, dt: datetime) -> float:
    return business_rules["demand"]["weekday_multipliers"][_WEEKDAY_NAMES[dt.weekday()]]


def _daypart_for_hour(hour: float, business_rules: dict) -> Daypart | None:
    lunch_start, _, lunch_end = _daypart_bounds(business_rules, "lunch")
    dinner_start, _, dinner_end = _daypart_bounds(business_rules, "dinner")
    if lunch_start <= hour < lunch_end:
        return "lunch"
    if dinner_start <= hour < dinner_end:
        return "dinner"
    return None


def arrival_rate_per_hour(dt: datetime, business_rules: dict, average_daily_orders: float) -> float:
    """Expected orders/hour at this exact moment."""
    hour = dt.hour + dt.minute / 60 + dt.second / 3600
    expected_today = average_daily_orders * _weekday_multiplier(business_rules, dt)
    return expected_today * _intraday_intensity(hour, business_rules)


def _sample_item_count(weights: dict[int, float], rng: np.random.Generator) -> int:
    counts = list(weights.keys())
    probabilities = list(weights.values())
    return int(rng.choice(counts, p=probabilities))


def _sample_channel(probabilities: dict[Channel, float], rng: np.random.Generator) -> Channel:
    channels = list(probabilities.keys())
    weights = list(probabilities.values())
    return str(rng.choice(channels, p=weights))


class LiveOrderSimulator:
    def __init__(
        self,
        business_rules: dict,
        average_daily_orders: float,
        average_item_price: float,
        channel_probabilities: dict[Channel, float],
        rng: np.random.Generator,
    ) -> None:
        self._business_rules = business_rules
        self._average_daily_orders = average_daily_orders
        self._average_item_price = average_item_price
        self._channel_probabilities = channel_probabilities
        self._rng = rng
        max_weekday_multiplier = max(business_rules["demand"]["weekday_multipliers"].values())
        self._lambda_max = (
            average_daily_orders * max_weekday_multiplier * _max_intraday_intensity(business_rules)
        )

    def _make_event(self, timestamp: datetime) -> OrderEvent:
        hour = timestamp.hour + timestamp.minute / 60
        daypart = _daypart_for_hour(hour, self._business_rules) or "dinner"
        item_count = _sample_item_count(
            self._business_rules["demand"]["items_per_order_weights"], self._rng
        )
        noise = self._rng.lognormal(mean=0.0, sigma=0.2)
        subtotal = round(item_count * self._average_item_price * noise, 2)
        return OrderEvent(
            event_id=str(uuid.uuid4()),
            timestamp=timestamp,
            channel=_sample_channel(self._channel_probabilities, self._rng),
            daypart=daypart,
            item_count=item_count,
            subtotal=subtotal,
        )

    def _next_arrival(self, sim_time: datetime) -> tuple[datetime, OrderEvent]:
        while True:
            hours_until_candidate = self._rng.exponential(1.0 / self._lambda_max)
            sim_time = sim_time + timedelta(hours=hours_until_candidate)
            rate = arrival_rate_per_hour(sim_time, self._business_rules, self._average_daily_orders)
            if rate <= 0:
                continue
            if self._rng.random() < rate / self._lambda_max:
                return sim_time, self._make_event(sim_time)

    def generate_events(self, start_time: datetime, duration_hours: float) -> list[OrderEvent]:
        """Pure/deterministic (given `rng`): every event arriving in
        `[start_time, start_time + duration_hours)`. No sleeping — used
        directly by tests and by `stream()`'s lookahead batching."""
        end_time = start_time + timedelta(hours=duration_hours)
        events = []
        sim_time = start_time
        while True:
            sim_time, event = self._next_arrival(sim_time)
            if sim_time >= end_time:
                break
            events.append(event)
        return events

    async def stream(
        self, *, start_time: datetime | None = None, time_scale: float = 60.0
    ) -> AsyncIterator[OrderEvent]:
        """Yield events in real time. `time_scale` simulated hours pass
        per real hour is 1.0; the default 60.0 means one simulated hour
        passes per real minute, so a full day's rhythm (quiet mornings,
        lunch/dinner rushes) plays out in ~20 real minutes instead of a day.
        """
        sim_time = start_time or datetime.now()
        while True:
            next_time, event = self._next_arrival(sim_time)
            real_delay_seconds = (next_time - sim_time).total_seconds() / time_scale
            await asyncio.sleep(real_delay_seconds)
            sim_time = next_time
            yield event


def default_start_time() -> datetime:
    """A simulated-clock start time inside today's lunch window.

    A freshly started live demo should begin producing orders almost
    immediately, not sit at zero for however many real hours happen to
    separate "now" from the next open service window — the arrival-rate
    function only depends on the *simulated* clock, so starting it
    inside a known-open window is free and has no downside.
    """
    # +30 minutes: the triangular intensity function is 0 exactly at a
    # window's own boundary (as any triangular density is at its edges),
    # so starting there would need a moment to warm up. Half an hour in
    # is unambiguously inside the window with positive density.
    business_rules = get_business_rules()
    lunch_start_hour = business_rules["dayparts"]["lunch"]["start_hour"]
    today = datetime.now().date()
    return datetime.combine(today, datetime.min.time()) + timedelta(
        hours=lunch_start_hour, minutes=30
    )


def build_default_simulator(rng: np.random.Generator) -> LiveOrderSimulator:
    """Wires the simulator to this project's real config and seed data —
    the average item price comes from `data/seed/menu_items.csv`, not a
    made-up number."""
    business_rules = get_business_rules()
    simulation_settings = get_simulation_settings()
    menu_items = load_menu_items()
    average_item_price = sum(item.selling_price for item in menu_items) / len(menu_items)
    channel_probabilities = {
        name: cfg.probability for name, cfg in simulation_settings.channels.items()
    }
    return LiveOrderSimulator(
        business_rules=business_rules,
        average_daily_orders=simulation_settings.simulation.average_daily_orders,
        average_item_price=average_item_price,
        channel_probabilities=channel_probabilities,
        rng=rng,
    )

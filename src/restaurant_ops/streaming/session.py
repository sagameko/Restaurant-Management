"""Full-session order history and summary — a companion to
aggregator.py's rolling window. That window only ever keeps the
trailing 15 minutes (correct for its job); this module keeps the fuller
session for pages that need more than a rolling snapshot. Plain Python
(a deque + a pure function), same proportionate style as aggregator.py.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

from restaurant_ops.streaming.events import OrderEvent

# A demo process, not a service meant to run indefinitely — 500 events
# is comfortably enough for the History page to be interesting without
# unbounded memory growth.
SESSION_HISTORY_LIMIT = 500


@dataclass
class SessionSummary:
    session_start: datetime
    session_duration_minutes: float
    total_orders: int
    total_revenue: float
    busiest_channel: str | None
    orders_by_channel: dict[str, int]
    peak_orders_per_minute: int


class SessionHistory:
    def __init__(self, maxlen: int = SESSION_HISTORY_LIMIT) -> None:
        self._events: deque[OrderEvent] = deque(maxlen=maxlen)

    def add(self, event: OrderEvent) -> None:
        self._events.append(event)

    @property
    def events(self) -> list[OrderEvent]:
        return list(self._events)


def compute_session_summary(events: list[OrderEvent], session_start: datetime) -> SessionSummary:
    """Pure function over a snapshot of events — mirrors
    RollingWindowAggregator.snapshot()'s shape. `session_start` must be
    the same simulated-clock value passed to `simulator.stream(...)`
    (`default_start_time()`), not `datetime.now()` — session duration
    has to be measured in the same clock the event timestamps use.
    """
    total_orders = len(events)
    total_revenue = round(sum(e.subtotal for e in events), 2)

    orders_by_channel: dict[str, int] = {}
    for event in events:
        orders_by_channel[event.channel] = orders_by_channel.get(event.channel, 0) + 1
    busiest_channel = (
        max(orders_by_channel, key=orders_by_channel.get) if orders_by_channel else None
    )

    orders_per_minute: dict[datetime, int] = {}
    for event in events:
        minute = event.timestamp.replace(second=0, microsecond=0)
        orders_per_minute[minute] = orders_per_minute.get(minute, 0) + 1
    peak_orders_per_minute = max(orders_per_minute.values()) if orders_per_minute else 0

    latest_timestamp = max((e.timestamp for e in events), default=session_start)
    session_duration_minutes = max((latest_timestamp - session_start).total_seconds() / 60.0, 0.0)

    return SessionSummary(
        session_start=session_start,
        session_duration_minutes=round(session_duration_minutes, 2),
        total_orders=total_orders,
        total_revenue=total_revenue,
        busiest_channel=busiest_channel,
        orders_by_channel=orders_by_channel,
        peak_orders_per_minute=peak_orders_per_minute,
    )

"""The real-time processing piece: a sliding-window KPI rollup over the
live event stream. Plain Python (a deque), not an external stream-
processing framework — proportionate to the actual event volume here.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from restaurant_ops.streaming.events import OrderEvent


@dataclass
class LiveSummary:
    window_minutes: float
    order_count: int
    total_revenue: float
    average_items_per_order: float
    orders_by_channel: dict[str, int]


class RollingWindowAggregator:
    def __init__(self, window_minutes: float = 15.0) -> None:
        self._window = timedelta(minutes=window_minutes)
        self._window_minutes = window_minutes
        self._events: deque[OrderEvent] = deque()

    def add(self, event: OrderEvent) -> None:
        self._events.append(event)
        self._evict(reference_time=event.timestamp)

    def _evict(self, reference_time: datetime) -> None:
        cutoff = reference_time - self._window
        while self._events and self._events[0].timestamp < cutoff:
            self._events.popleft()

    def snapshot(self, reference_time: datetime | None = None) -> LiveSummary:
        if reference_time is not None:
            self._evict(reference_time)
        elif self._events:
            self._evict(self._events[-1].timestamp)

        events = list(self._events)
        order_count = len(events)
        total_revenue = sum(e.subtotal for e in events)
        average_items = sum(e.item_count for e in events) / order_count if order_count else 0.0

        orders_by_channel: dict[str, int] = {}
        for e in events:
            orders_by_channel[e.channel] = orders_by_channel.get(e.channel, 0) + 1

        return LiveSummary(
            window_minutes=self._window_minutes,
            order_count=order_count,
            total_revenue=round(total_revenue, 2),
            average_items_per_order=round(average_items, 2),
            orders_by_channel=orders_by_channel,
        )

    def recent_events(self, limit: int = 20) -> list[OrderEvent]:
        return list(self._events)[-limit:]

"""The live order-event schema.

Deliberately simpler than the batch `Order`/`OrderItem` pair in
`ingestion/schemas.py` — this layer is about live event *flow*
(something arrives, something changes state), not re-deriving food
cost, inventory, or staffing in real time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Channel = Literal["dine_in", "pickup", "uber_eats", "doordash"]
Daypart = Literal["lunch", "dinner"]
OrderStatus = Literal["placed", "in_kitchen", "ready", "completed"]


class OrderEvent(BaseModel):
    event_id: str
    timestamp: datetime
    channel: Channel
    daypart: Daypart
    item_count: int = Field(gt=0)
    subtotal: float = Field(gt=0)
    status: OrderStatus = "placed"

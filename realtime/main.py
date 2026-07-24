"""FastAPI app for the live order feed.

Thin consumer of `restaurant_ops.streaming` — mirrors how `app/` is a
thin Streamlit consumer of the rest of `restaurant_ops`: the actual
event generation and rolling-window aggregation logic lives in the
package, not here.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from restaurant_ops.streaming.aggregator import LiveSummary, RollingWindowAggregator
from restaurant_ops.streaming.simulator import build_default_simulator

AGGREGATOR_WINDOW_MINUTES = 15.0
# Simulated hours that pass per real hour. 60 -> a full day's rhythm
# (quiet mornings, lunch/dinner rushes) plays out in ~20 real minutes.
TIME_SCALE = 60.0

aggregator = RollingWindowAggregator(window_minutes=AGGREGATOR_WINDOW_MINUTES)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        stale = []
        for connection in self._connections:
            try:
                await connection.send_json(message)
            except Exception:  # noqa: BLE001
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)


manager = ConnectionManager()


def _summary_payload(summary: LiveSummary) -> dict:
    return {
        "window_minutes": summary.window_minutes,
        "order_count": summary.order_count,
        "total_revenue": summary.total_revenue,
        "average_items_per_order": summary.average_items_per_order,
        "orders_by_channel": summary.orders_by_channel,
    }


async def _run_simulator() -> None:
    rng = np.random.default_rng()
    simulator = build_default_simulator(rng)
    async for event in simulator.stream(time_scale=TIME_SCALE):
        aggregator.add(event)
        await manager.broadcast(
            {
                "type": "order",
                "event": event.model_dump(mode="json"),
                "summary": _summary_payload(aggregator.snapshot(event.timestamp)),
            }
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(_run_simulator())
    yield
    task.cancel()


app = FastAPI(title="Restaurant Ops — Live", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/live/summary")
def get_summary() -> dict:
    return _summary_payload(aggregator.snapshot())


@app.websocket("/ws/orders")
async def orders_ws(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    await websocket.send_json(
        {"type": "summary", "summary": _summary_payload(aggregator.snapshot())}
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

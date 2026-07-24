import { describe, expect, it } from "vitest"
import { bucketOrdersByMinute } from "./buckets"
import type { OrderEvent } from "./types"

function makeEvent(timestamp: string, overrides: Partial<OrderEvent> = {}): OrderEvent {
  return {
    event_id: `evt-${timestamp}`,
    timestamp,
    channel: "dine_in",
    daypart: "lunch",
    item_count: 2,
    subtotal: 25,
    status: "placed",
    ...overrides,
  }
}

describe("bucketOrdersByMinute", () => {
  it("returns an empty array for no events", () => {
    expect(bucketOrdersByMinute([])).toEqual([])
  })

  it("groups events into their own minute bucket", () => {
    const events = [
      makeEvent("2026-01-05T12:00:10Z"),
      makeEvent("2026-01-05T12:00:40Z"),
      makeEvent("2026-01-05T12:01:05Z"),
    ]

    const buckets = bucketOrdersByMinute(events)

    expect(buckets).toEqual([
      { minute: "2026-01-05T12:00:00.000Z", count: 2 },
      { minute: "2026-01-05T12:01:00.000Z", count: 1 },
    ])
  })

  it("anchors the trailing window to the latest event timestamp, not real time", () => {
    // These timestamps are deliberately far from the real "now" the
    // test runs at (the simulator's clock is compressed via time_scale
    // and has no relation to wall-clock time) — bucketing must still
    // work purely off the events' own timestamps.
    const events = [
      makeEvent("2020-06-01T09:00:00Z"),
      makeEvent("2020-06-01T09:20:00Z"),
      makeEvent("2020-06-01T09:29:00Z"),
    ]

    const buckets = bucketOrdersByMinute(events, 15)

    // The 09:00 event is outside the 15-minute trailing window anchored
    // at the latest event (09:29), so only the last two survive.
    expect(buckets.map((b) => b.minute)).toEqual([
      "2020-06-01T09:20:00.000Z",
      "2020-06-01T09:29:00.000Z",
    ])
  })
})

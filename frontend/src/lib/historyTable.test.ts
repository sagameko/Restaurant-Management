import { describe, expect, it } from "vitest"
import { filterAndSortHistory } from "./historyTable"
import type { OrderEvent } from "./types"

function makeEvent(overrides: Partial<OrderEvent>): OrderEvent {
  return {
    event_id: "evt-1",
    timestamp: "2026-01-05T12:00:00Z",
    channel: "dine_in",
    daypart: "lunch",
    item_count: 2,
    subtotal: 25,
    status: "placed",
    ...overrides,
  }
}

describe("filterAndSortHistory", () => {
  const events = [
    makeEvent({ event_id: "a", channel: "dine_in", subtotal: 40, timestamp: "2026-01-05T12:00:00Z" }),
    makeEvent({ event_id: "b", channel: "uber_eats", subtotal: 10, timestamp: "2026-01-05T12:05:00Z" }),
    makeEvent({ event_id: "c", channel: "dine_in", subtotal: 20, timestamp: "2026-01-05T12:02:00Z" }),
  ]

  it("defaults to newest-first by timestamp", () => {
    const result = filterAndSortHistory(events)
    expect(result.map((e) => e.event_id)).toEqual(["b", "c", "a"])
  })

  it("filters by channel", () => {
    const result = filterAndSortHistory(events, { channelFilter: "dine_in" })
    expect(result.map((e) => e.event_id)).toEqual(["c", "a"])
  })

  it("sorts by a numeric column ascending", () => {
    const result = filterAndSortHistory(events, { sortColumn: "subtotal", sortDirection: "asc" })
    expect(result.map((e) => e.event_id)).toEqual(["b", "c", "a"])
  })

  it("does not mutate the input array", () => {
    const original = [...events]
    filterAndSortHistory(events, { sortColumn: "subtotal", sortDirection: "asc" })
    expect(events).toEqual(original)
  })
})

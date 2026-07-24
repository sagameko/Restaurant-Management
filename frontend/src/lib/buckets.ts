import type { OrderEvent } from "./types"

export interface OrderBucket {
  minute: string
  count: number
}

/** Buckets events into per-minute counts over a trailing window.
 *
 * Event timestamps are the simulator's own *simulated* clock
 * (compressed via time_scale), not real wall-clock time, so the
 * trailing window has to anchor to the latest event's own timestamp,
 * never to the browser's Date.now().
 */
export function bucketOrdersByMinute(events: OrderEvent[], windowMinutes = 15): OrderBucket[] {
  if (events.length === 0) return []

  const latestMs = events.reduce((max, e) => Math.max(max, Date.parse(e.timestamp)), 0)
  const cutoffMs = latestMs - windowMinutes * 60_000

  const counts = new Map<number, number>()
  for (const event of events) {
    const ms = Date.parse(event.timestamp)
    if (ms < cutoffMs) continue
    const minuteMs = Math.floor(ms / 60_000) * 60_000
    counts.set(minuteMs, (counts.get(minuteMs) ?? 0) + 1)
  }

  return Array.from(counts.entries())
    .sort(([a], [b]) => a - b)
    .map(([minuteMs, count]) => ({ minute: new Date(minuteMs).toISOString(), count }))
}

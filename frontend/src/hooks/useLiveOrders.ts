import { useEffect, useMemo, useState } from "react"
import { bucketOrdersByMinute } from "../lib/buckets"
import type { OrderBucket } from "../lib/buckets"
import type { LiveSummary, OrderEvent } from "../lib/types"
import { LiveOrdersClient } from "../lib/websocket"
import type { ConnectionStatus } from "../lib/websocket"

const FEED_LIMIT = 30
// Enough events to cover a full 15-minute rolling window at plausible
// order rates for this chart, independent of the scrolling feed's
// much smaller display limit above.
const CHART_BUFFER_LIMIT = 1000

export interface UseLiveOrdersResult {
  status: ConnectionStatus
  summary: LiveSummary | null
  feed: OrderEvent[]
  buckets: OrderBucket[]
}

export function useLiveOrders(): UseLiveOrdersResult {
  const [status, setStatus] = useState<ConnectionStatus>("connecting")
  const [summary, setSummary] = useState<LiveSummary | null>(null)
  const [feed, setFeed] = useState<OrderEvent[]>([])
  const [chartEvents, setChartEvents] = useState<OrderEvent[]>([])

  useEffect(() => {
    const client = new LiveOrdersClient({
      onStatusChange: setStatus,
      onMessage: (message) => {
        setSummary(message.summary)
        if (message.type === "order") {
          setFeed((prev) => [message.event, ...prev].slice(0, FEED_LIMIT))
          setChartEvents((prev) => [...prev, message.event].slice(-CHART_BUFFER_LIMIT))
        }
      },
    })
    client.connect()
    return () => client.close()
  }, [])

  const buckets = useMemo(() => bucketOrdersByMinute(chartEvents), [chartEvents])

  return { status, summary, feed, buckets }
}

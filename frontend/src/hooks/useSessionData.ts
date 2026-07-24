import { useEffect, useState } from "react"
import { resolveApiBaseUrl } from "../lib/api"
import type { OrderEvent, SessionSummary } from "../lib/types"

const POLL_INTERVAL_MS = 5000

export interface UseSessionDataResult {
  history: OrderEvent[]
  sessionSummary: SessionSummary | null
}

// Deliberately separate from useLiveOrders's WebSocket path — Order
// History and Session Analytics aren't the primary live-updating view,
// so simple polling keeps the WS message contract untouched.
export function useSessionData(): UseSessionDataResult {
  const [history, setHistory] = useState<OrderEvent[]>([])
  const [sessionSummary, setSessionSummary] = useState<SessionSummary | null>(null)

  useEffect(() => {
    const base = resolveApiBaseUrl()
    let cancelled = false

    async function poll() {
      try {
        const [historyRes, summaryRes] = await Promise.all([
          fetch(`${base}/api/live/history`),
          fetch(`${base}/api/live/session-summary`),
        ])
        if (cancelled) return
        if (historyRes.ok) setHistory(await historyRes.json())
        if (summaryRes.ok) setSessionSummary(await summaryRes.json())
      } catch {
        // Transient network error — the next poll retries.
      }
    }

    poll()
    const timer = setInterval(poll, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  return { history, sessionSummary }
}

import { ChannelBreakdown } from "../components/ChannelBreakdown"
import { KpiCard } from "../components/KpiCard"
import { useSessionData } from "../hooks/useSessionData"
import { channelLabel } from "../lib/palette"

function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60)
  const mins = Math.round(minutes % 60)
  return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`
}

export function SessionAnalytics() {
  const { sessionSummary } = useSessionData()

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-neutral-900 dark:text-neutral-50">Session Analytics</h1>
      <p className="text-sm text-neutral-500">
        Cumulative stats since the server started — distinct from Live Operations&rsquo; rolling
        15-minute window.
      </p>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <KpiCard label="Total orders" value={sessionSummary ? String(sessionSummary.total_orders) : "—"} />
        <KpiCard
          label="Total revenue"
          value={sessionSummary ? `$${sessionSummary.total_revenue.toFixed(2)}` : "—"}
        />
        <KpiCard
          label="Busiest channel"
          value={sessionSummary?.busiest_channel ? channelLabel(sessionSummary.busiest_channel) : "—"}
        />
        <KpiCard
          label="Peak orders/min"
          value={sessionSummary ? String(sessionSummary.peak_orders_per_minute) : "—"}
        />
        <KpiCard
          label="Session duration"
          value={sessionSummary ? formatDuration(sessionSummary.session_duration_minutes) : "—"}
        />
      </div>

      <div className="max-w-md rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-700 dark:bg-neutral-900">
        <h2 className="mb-3 text-sm font-medium text-neutral-700 dark:text-neutral-200">
          Orders by channel (session)
        </h2>
        <ChannelBreakdown ordersByChannel={sessionSummary?.orders_by_channel ?? {}} />
      </div>
    </div>
  )
}

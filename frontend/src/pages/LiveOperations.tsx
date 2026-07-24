import { ChannelBreakdown } from "../components/ChannelBreakdown"
import { KpiCard } from "../components/KpiCard"
import { LiveChart } from "../components/LiveChart"
import { OrderFeed } from "../components/OrderFeed"
import type { UseLiveOrdersResult } from "../hooks/useLiveOrders"

interface LiveOperationsProps {
  live: UseLiveOrdersResult
}

export function LiveOperations({ live }: LiveOperationsProps) {
  const { summary, feed, buckets } = live

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-neutral-900 dark:text-neutral-50">Live Operations</h1>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KpiCard label="Orders (15 min)" value={summary ? String(summary.order_count) : "—"} />
        <KpiCard label="Revenue (15 min)" value={summary ? `$${summary.total_revenue.toFixed(2)}` : "—"} />
        <KpiCard
          label="Avg items / order"
          value={summary ? summary.average_items_per_order.toFixed(1) : "—"}
        />
        <KpiCard label="Window" value={summary ? `${summary.window_minutes} min` : "—"} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-700 dark:bg-neutral-900 lg:col-span-2">
          <h2 className="mb-3 text-sm font-medium text-neutral-700 dark:text-neutral-200">Orders per minute</h2>
          <LiveChart buckets={buckets} />
        </div>
        <div className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-700 dark:bg-neutral-900">
          <h2 className="mb-3 text-sm font-medium text-neutral-700 dark:text-neutral-200">Channel breakdown</h2>
          <ChannelBreakdown ordersByChannel={summary?.orders_by_channel ?? {}} />
        </div>
      </div>

      <div className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-700 dark:bg-neutral-900">
        <h2 className="mb-3 text-sm font-medium text-neutral-700 dark:text-neutral-200">Order feed</h2>
        <OrderFeed events={feed} />
      </div>
    </div>
  )
}

import { channelLabel, colorForChannel } from "../lib/palette"

interface ChannelBreakdownProps {
  ordersByChannel: Record<string, number>
}

export function ChannelBreakdown({ ordersByChannel }: ChannelBreakdownProps) {
  const total = Object.values(ordersByChannel).reduce((sum, n) => sum + n, 0)
  const entries = Object.entries(ordersByChannel).sort(([, a], [, b]) => b - a)

  if (entries.length === 0) {
    return <p className="text-sm text-neutral-500">No orders yet.</p>
  }

  return (
    <div className="space-y-3">
      {entries.map(([channel, count]) => {
        const pct = total > 0 ? (count / total) * 100 : 0
        return (
          <div key={channel}>
            <div className="mb-1 flex justify-between text-sm">
              <span className="text-neutral-700 dark:text-neutral-200">{channelLabel(channel)}</span>
              <span className="tabular-nums text-neutral-500">{count}</span>
            </div>
            <div className="h-2 w-full rounded-full bg-neutral-100 dark:bg-neutral-800">
              <div
                className="h-2 rounded-full transition-[width]"
                style={{ width: `${pct}%`, backgroundColor: colorForChannel(channel) }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

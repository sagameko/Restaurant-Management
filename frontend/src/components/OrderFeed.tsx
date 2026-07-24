import { channelLabel } from "../lib/palette"
import type { OrderEvent } from "../lib/types"

interface OrderFeedProps {
  events: OrderEvent[]
}

export function OrderFeed({ events }: OrderFeedProps) {
  if (events.length === 0) {
    return <p className="text-sm text-neutral-500">Waiting for orders…</p>
  }

  return (
    <ul className="max-h-96 divide-y divide-neutral-100 overflow-y-auto dark:divide-neutral-800">
      {events.map((event) => (
        <li key={event.event_id} className="flex items-center justify-between gap-3 py-2 text-sm">
          <span className="font-medium text-neutral-700 dark:text-neutral-200">{channelLabel(event.channel)}</span>
          <span className="text-neutral-500">{event.item_count} items</span>
          <span className="tabular-nums text-neutral-700 dark:text-neutral-200">
            ${event.subtotal.toFixed(2)}
          </span>
          <span className="tabular-nums text-neutral-400">
            {new Date(event.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </span>
        </li>
      ))}
    </ul>
  )
}

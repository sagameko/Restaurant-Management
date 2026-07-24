import type { OrderEvent } from "./types"

export type SortColumn = "timestamp" | "channel" | "daypart" | "item_count" | "subtotal"
export type SortDirection = "asc" | "desc"

export interface HistoryTableOptions {
  channelFilter?: string | "all"
  sortColumn?: SortColumn
  sortDirection?: SortDirection
}

export function filterAndSortHistory(
  events: OrderEvent[],
  { channelFilter = "all", sortColumn = "timestamp", sortDirection = "desc" }: HistoryTableOptions = {},
): OrderEvent[] {
  const filtered = channelFilter === "all" ? events : events.filter((e) => e.channel === channelFilter)

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortColumn]
    const bv = b[sortColumn]
    if (av < bv) return -1
    if (av > bv) return 1
    return 0
  })

  if (sortDirection === "desc") sorted.reverse()
  return sorted
}

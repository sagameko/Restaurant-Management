import { useMemo, useState } from "react"
import { useSessionData } from "../hooks/useSessionData"
import { filterAndSortHistory } from "../lib/historyTable"
import type { SortColumn, SortDirection } from "../lib/historyTable"
import { channelLabel } from "../lib/palette"

const CHANNELS = ["all", "dine_in", "pickup", "uber_eats", "doordash"]

const COLUMNS: { key: SortColumn; label: string }[] = [
  { key: "timestamp", label: "Time" },
  { key: "channel", label: "Channel" },
  { key: "daypart", label: "Daypart" },
  { key: "item_count", label: "Items" },
  { key: "subtotal", label: "Subtotal" },
]

export function OrderHistory() {
  const { history } = useSessionData()
  const [channelFilter, setChannelFilter] = useState<string>("all")
  const [sortColumn, setSortColumn] = useState<SortColumn>("timestamp")
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc")

  const rows = useMemo(
    () => filterAndSortHistory(history, { channelFilter, sortColumn, sortDirection }),
    [history, channelFilter, sortColumn, sortDirection],
  )

  function toggleSort(column: SortColumn) {
    if (column === sortColumn) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"))
    } else {
      setSortColumn(column)
      setSortDirection("desc")
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-neutral-900 dark:text-neutral-50">Order History</h1>
        <select
          value={channelFilter}
          onChange={(e) => setChannelFilter(e.target.value)}
          className="rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          {CHANNELS.map((c) => (
            <option key={c} value={c}>
              {c === "all" ? "All channels" : channelLabel(c)}
            </option>
          ))}
        </select>
      </div>

      <p className="text-sm text-neutral-500">
        {history.length} order{history.length === 1 ? "" : "s"} seen this session (last 500 kept).
      </p>

      <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-700">
        <table className="min-w-full divide-y divide-neutral-200 text-sm dark:divide-neutral-700">
          <thead className="bg-neutral-50 dark:bg-neutral-900">
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  onClick={() => toggleSort(col.key)}
                  className="cursor-pointer select-none px-3 py-2 text-left font-medium text-neutral-600 dark:text-neutral-300"
                >
                  {col.label}
                  {sortColumn === col.key ? (sortDirection === "asc" ? " ▲" : " ▼") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800">
            {rows.map((event) => (
              <tr key={event.event_id}>
                <td className="px-3 py-2 tabular-nums text-neutral-500">
                  {new Date(event.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </td>
                <td className="px-3 py-2">{channelLabel(event.channel)}</td>
                <td className="px-3 py-2 capitalize">{event.daypart}</td>
                <td className="px-3 py-2 tabular-nums">{event.item_count}</td>
                <td className="px-3 py-2 tabular-nums">${event.subtotal.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="p-4 text-sm text-neutral-500">No orders yet.</p>}
      </div>
    </div>
  )
}

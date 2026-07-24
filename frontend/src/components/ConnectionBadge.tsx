import type { ConnectionStatus } from "../lib/websocket"

const LABELS: Record<ConnectionStatus, string> = {
  connecting: "Reconnecting…",
  open: "Live",
  closed: "Disconnected",
}

const DOT_COLOR: Record<ConnectionStatus, string> = {
  connecting: "bg-amber-500",
  open: "bg-emerald-500",
  closed: "bg-red-500",
}

export function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-neutral-500 dark:text-neutral-400">
      <span className={`h-2 w-2 rounded-full ${DOT_COLOR[status]}`} />
      {LABELS[status]}
    </span>
  )
}

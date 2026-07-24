import { NavLink } from "react-router-dom"
import type { ConnectionStatus } from "../lib/websocket"
import { ConnectionBadge } from "./ConnectionBadge"

const LINKS = [
  { to: "/", label: "Live Operations" },
  { to: "/history", label: "Order History" },
  { to: "/analytics", label: "Session Analytics" },
  { to: "/about", label: "About" },
]

interface NavProps {
  status: ConnectionStatus
}

export function Nav({ status }: NavProps) {
  return (
    <nav className="flex items-center justify-between border-b border-neutral-200 px-6 py-3 dark:border-neutral-700">
      <div className="flex items-center gap-6">
        <span className="font-semibold text-neutral-900 dark:text-neutral-50">Restaurant Ops — Live</span>
        <div className="flex gap-4 text-sm">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                isActive
                  ? "font-medium text-neutral-900 dark:text-neutral-50"
                  : "text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200"
              }
            >
              {link.label}
            </NavLink>
          ))}
        </div>
      </div>
      <ConnectionBadge status={status} />
    </nav>
  )
}

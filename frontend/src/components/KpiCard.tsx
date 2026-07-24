interface KpiCardProps {
  label: string
  value: string
  hint?: string
}

export function KpiCard({ label, value, hint }: KpiCardProps) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm dark:border-neutral-700 dark:bg-neutral-900">
      <div className="text-xs font-medium uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold text-neutral-900 dark:text-neutral-50">{value}</div>
      {hint && <div className="mt-1 text-xs text-neutral-400">{hint}</div>}
    </div>
  )
}

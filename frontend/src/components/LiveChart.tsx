import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import type { OrderBucket } from "../lib/buckets"

interface LiveChartProps {
  buckets: OrderBucket[]
}

export function LiveChart({ buckets }: LiveChartProps) {
  const data = buckets.map((bucket) => ({
    time: new Date(bucket.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    count: bucket.count,
  }))

  if (data.length === 0) {
    return <p className="text-sm text-neutral-500">Waiting for orders…</p>
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis dataKey="time" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={30} />
          <Tooltip />
          <Line type="monotone" dataKey="count" stroke="#2a78d6" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

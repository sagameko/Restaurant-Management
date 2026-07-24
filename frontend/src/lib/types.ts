// Mirrors src/restaurant_ops/streaming/events.py and the JSON shapes
// realtime/main.py sends over REST/WebSocket. Hand-kept in sync — same
// trade-off already accepted for dim_channel's commission rates.

export type Channel = "dine_in" | "pickup" | "uber_eats" | "doordash"
export type Daypart = "lunch" | "dinner"
export type OrderStatus = "placed" | "in_kitchen" | "ready" | "completed"

export interface OrderEvent {
  event_id: string
  timestamp: string
  channel: Channel
  daypart: Daypart
  item_count: number
  subtotal: number
  status: OrderStatus
}

export interface LiveSummary {
  window_minutes: number
  order_count: number
  total_revenue: number
  average_items_per_order: number
  orders_by_channel: Record<string, number>
}

export interface SessionSummary {
  session_start: string
  session_duration_minutes: number
  total_orders: number
  total_revenue: number
  busiest_channel: string | null
  orders_by_channel: Record<string, number>
  peak_orders_per_minute: number
}

export type LiveMessage =
  | { type: "order"; event: OrderEvent; summary: LiveSummary }
  | { type: "summary"; summary: LiveSummary }

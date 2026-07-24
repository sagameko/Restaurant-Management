// Same validated categorical hex order as app/components/charts.py's
// CATEGORICAL, so channel colors match between the Streamlit dashboard
// and this app. Colors are assigned by a fixed channel order — never
// re-cycled or re-sorted — so a channel's color stays stable across
// pages and charts, mirroring the convention charts.py documents.

export const CATEGORICAL = [
  "#2a78d6", // blue
  "#eb6834", // orange
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
]

const CHANNEL_ORDER = ["dine_in", "pickup", "uber_eats", "doordash"]

export function colorForChannel(channel: string): string {
  const index = CHANNEL_ORDER.indexOf(channel)
  return CATEGORICAL[index >= 0 ? index : CHANNEL_ORDER.length % CATEGORICAL.length]
}

const CHANNEL_LABELS: Record<string, string> = {
  dine_in: "Dine-in",
  pickup: "Pickup",
  uber_eats: "Uber Eats",
  doordash: "DoorDash",
}

export function channelLabel(channel: string): string {
  return CHANNEL_LABELS[channel] ?? channel
}

import type { LiveMessage } from "./types"

export type ConnectionStatus = "connecting" | "open" | "closed"

// uv run uvicorn realtime.main:app --reload (the documented run
// command, no --host) binds to 127.0.0.1 only. On hosts where
// "localhost" resolves to ::1 first, a client targeting "localhost"
// hangs against a socket nothing is listening on — target 127.0.0.1
// directly to avoid that resolution mismatch.
const DEFAULT_WS_URL = "ws://127.0.0.1:8000/ws/orders"

export function resolveWsUrl(): string {
  const fromEnv = import.meta.env.VITE_WS_URL as string | undefined
  return fromEnv && fromEnv.length > 0 ? fromEnv : DEFAULT_WS_URL
}

export interface LiveOrdersClientOptions {
  url?: string
  onMessage: (message: LiveMessage) => void
  onStatusChange?: (status: ConnectionStatus) => void
  createSocket?: (url: string) => WebSocket
  minBackoffMs?: number
  maxBackoffMs?: number
}

export class LiveOrdersClient {
  private readonly url: string
  private readonly onMessage: (message: LiveMessage) => void
  private readonly onStatusChange: (status: ConnectionStatus) => void
  private readonly createSocket: (url: string) => WebSocket
  private readonly minBackoffMs: number
  private readonly maxBackoffMs: number

  private socket: WebSocket | null = null
  private backoffMs: number
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private closedByCaller = false

  constructor(options: LiveOrdersClientOptions) {
    this.url = options.url ?? resolveWsUrl()
    this.onMessage = options.onMessage
    this.onStatusChange = options.onStatusChange ?? (() => {})
    this.createSocket = options.createSocket ?? ((url) => new WebSocket(url))
    this.minBackoffMs = options.minBackoffMs ?? 500
    this.maxBackoffMs = options.maxBackoffMs ?? 8000
    this.backoffMs = this.minBackoffMs
  }

  connect(): void {
    this.closedByCaller = false
    this.open()
  }

  close(): void {
    this.closedByCaller = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.socket?.close()
  }

  private open(): void {
    this.onStatusChange("connecting")
    const socket = this.createSocket(this.url)
    this.socket = socket

    socket.onopen = () => {
      this.backoffMs = this.minBackoffMs
      this.onStatusChange("open")
    }

    socket.onmessage = (event: MessageEvent) => {
      const data = JSON.parse(event.data as string) as LiveMessage
      this.onMessage(data)
    }

    socket.onclose = () => {
      this.onStatusChange("closed")
      this.scheduleReconnect()
    }

    socket.onerror = () => {
      socket.close()
    }
  }

  private scheduleReconnect(): void {
    if (this.closedByCaller) return
    this.reconnectTimer = setTimeout(() => {
      this.backoffMs = Math.min(this.backoffMs * 2, this.maxBackoffMs)
      this.open()
    }, this.backoffMs)
  }
}

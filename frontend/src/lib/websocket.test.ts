import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { LiveOrdersClient } from "./websocket"
import type { ConnectionStatus } from "./websocket"
import type { LiveMessage } from "./types"

class MockSocket {
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false

  close(): void {
    this.closed = true
    this.onclose?.()
  }

  triggerOpen(): void {
    this.onopen?.()
  }

  triggerMessage(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) })
  }
}

describe("LiveOrdersClient", () => {
  let sockets: MockSocket[]
  let statuses: ConnectionStatus[]
  let messages: LiveMessage[]

  beforeEach(() => {
    vi.useFakeTimers()
    sockets = []
    statuses = []
    messages = []
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function makeClient(): LiveOrdersClient {
    return new LiveOrdersClient({
      onMessage: (m) => messages.push(m),
      onStatusChange: (s) => statuses.push(s),
      createSocket: () => {
        const socket = new MockSocket()
        sockets.push(socket)
        return socket as unknown as WebSocket
      },
    })
  }

  it("reports connecting then open on a successful connection", () => {
    const client = makeClient()
    client.connect()
    expect(statuses).toEqual(["connecting"])

    sockets[0].triggerOpen()
    expect(statuses).toEqual(["connecting", "open"])
  })

  it("parses incoming messages and forwards them", () => {
    const client = makeClient()
    client.connect()
    sockets[0].triggerOpen()

    const summary: LiveMessage = {
      type: "summary",
      summary: {
        window_minutes: 15,
        order_count: 3,
        total_revenue: 99.5,
        average_items_per_order: 2,
        orders_by_channel: { dine_in: 3 },
      },
    }
    sockets[0].triggerMessage(summary)

    expect(messages).toEqual([summary])
  })

  it("reconnects with growing backoff after the socket closes", () => {
    const client = makeClient()
    client.connect()
    sockets[0].close()

    expect(statuses).toEqual(["connecting", "closed"])
    expect(sockets).toHaveLength(1)

    vi.advanceTimersByTime(500)
    expect(sockets).toHaveLength(2)

    sockets[1].close()
    vi.advanceTimersByTime(999)
    expect(sockets).toHaveLength(2) // backoff doubled to 1000ms, not yet due
    vi.advanceTimersByTime(1)
    expect(sockets).toHaveLength(3)
  })

  it("resets backoff to the minimum after a successful reconnect", () => {
    const client = makeClient()
    client.connect()
    sockets[0].close()
    vi.advanceTimersByTime(500)
    sockets[1].close()
    vi.advanceTimersByTime(1000)
    sockets[2].triggerOpen() // backoff resets here

    sockets[2].close()
    vi.advanceTimersByTime(499)
    expect(sockets).toHaveLength(3)
    vi.advanceTimersByTime(1)
    expect(sockets).toHaveLength(4)
  })

  it("does not reconnect once closed by the caller", () => {
    const client = makeClient()
    client.connect()
    client.close()

    expect(sockets[0].closed).toBe(true)
    vi.advanceTimersByTime(10_000)
    expect(sockets).toHaveLength(1)
  })
})

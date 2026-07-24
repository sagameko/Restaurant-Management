// Same host-resolution reasoning as websocket.ts: the documented run
// command (`uv run uvicorn realtime.main:app --reload`) binds to
// 127.0.0.1 only, so REST calls default there too rather than to
// "localhost".
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"

export function resolveApiBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_API_BASE_URL as string | undefined
  return fromEnv && fromEnv.length > 0 ? fromEnv : DEFAULT_API_BASE_URL
}

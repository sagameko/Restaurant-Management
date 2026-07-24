import { Route, Routes } from "react-router-dom"
import { Nav } from "./components/Nav"
import { useLiveOrders } from "./hooks/useLiveOrders"
import { About } from "./pages/About"
import { LiveOperations } from "./pages/LiveOperations"
import { OrderHistory } from "./pages/OrderHistory"
import { SessionAnalytics } from "./pages/SessionAnalytics"

function App() {
  const live = useLiveOrders()

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-950">
      <Nav status={live.status} />
      <main className="mx-auto max-w-5xl px-6 py-8">
        <div className="mb-6 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
          <strong>All data in this application is synthetic.</strong> Orders, staffing, inventory, and
          customer reviews are generated from configurable business rules — not real transactions,
          employees, or customers.
        </div>
        <Routes>
          <Route path="/" element={<LiveOperations live={live} />} />
          <Route path="/history" element={<OrderHistory />} />
          <Route path="/analytics" element={<SessionAnalytics />} />
          <Route path="/about" element={<About />} />
        </Routes>
      </main>
    </div>
  )
}

export default App

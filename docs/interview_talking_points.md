# Interview talking points

Scannable version of `docs/project_decisions.md` — things worth actually
saying out loud, grouped by theme. Each point is concrete and checkable
against this repo, not a generic claim.

## Data engineering

- Built a full synthetic data generator (weather/calendar, staffing,
  orders, inventory, reviews) where every required causal relationship —
  kitchen load → prep time → missing items → refunds → ratings —
  actually holds *directionally* in the generated data, not just in the
  formulas. Verified by querying grouped output after each phase, not by
  trusting that validation passing meant the relationship was real.
- A single seeded `numpy.random.Generator` threaded through every
  generator function makes a full year (39k+ orders, 88k+ order items,
  32k+ inventory movements) exactly reproducible from one `--seed`.
- Designed a per-ingredient inventory ledger (deliveries, consumption,
  waste, emergency same-day purchasing) that provably never goes
  negative — and found/fixed a subtle bug where the ledger was correct
  internally but *looked* like it went negative to anything re-deriving
  state by sorting on timestamp, because two movement types shared an
  hour-of-day default that didn't reflect true processing order.

## Analytics engineering (dbt + DuckDB)

- Layered warehouse: staging → intermediate → dimensions/facts → 7
  marts, each mart aligned 1:1 with a dashboard page, 98 dbt
  tests/models passing.
- Found and fixed a join fan-out that inflated one mart's profit figures
  by roughly 6 orders of magnitude (two fact-grain tables joined
  directly on a shared non-unique column before aggregating) — then
  audited every other mart for the same pattern rather than treating it
  as a one-off fix.
- Recompute-don't-trust pattern: intermediate models independently
  re-derive figures (e.g. menu-item food cost) in SQL rather than
  blindly trusting the upstream Python-computed column, catching
  divergence between the two layers.

## Forecasting

- Compared 4 models (naive, moving average, linear regression, random
  forest) with a strict chronological train/test split — explicitly
  never a random split, since that would leak future information into
  training for time-series data.
- Built the 7-day-ahead forecast to recursively feed its own predictions
  back in as lag features for days beyond the first (there's no other
  way a multi-step forecast can work), and wrote a specific unit test
  proving that recursion actually happens rather than silently using
  stale/real data it shouldn't have access to.
- Translated a predicted order count into a recommended headcount using
  only observed historical benchmarks (orders/labour-hour on
  known-"Balanced" days, real average shift length) — no new invented
  constants.

## Real-time / systems (in progress)

- Added a second, complementary showcase alongside the batch pipeline:
  a live order-event simulator and FastAPI/WebSocket API, deliberately
  *not* a message broker at this scale — a proper non-homogeneous
  Poisson process (thinning algorithm) instead of a naive random ticker,
  reusing the same demand-shape config the batch generator uses so the
  live feed's rhythm matches the historical dataset's.
- Deliberately kept the finished Streamlit dashboard as-is rather than
  folding it into a real-time rebuild — two purpose-built apps (batch BI,
  real-time ops) instead of one app straining to do both.
- Next: a React frontend consuming the WebSocket feed, then self-hosted
  deployment (Caddy + Docker Compose) behind a real domain.

## Testing and debugging philosophy

- 90+ tests: Pydantic validation for seed data, vectorised pandas checks
  for generated tables at scale, pure-function unit tests for
  forecasting/streaming logic, and one true end-to-end integration test
  (generate → load → `dbt build` → verify marts have rows).
- The recurring lesson across three separate bugs in three different
  phases: a green test suite doesn't prove the real data/UI matches what
  the code assumes. A dashboard once showed a per-unit price next to a
  total cost — only visible by looking at the *rendered* numbers
  together, not by reading the SQL and Python separately. Caught with a
  headless-browser screenshot, not a unit test.
- CI mirrors the real pipeline end to end (lint → test → generate → load
  → `dbt build` → verify marts) rather than just running unit tests —
  and a step-ordering bug in that exact workflow (a dbt profile file
  created *after* the test that needed it) only showed up on a genuinely
  clean CI checkout, not locally, where stale local state was quietly
  standing in for the missing step.

## What I'd do differently / next

- A rolling-origin (walk-forward) cross-validation for the forecast
  instead of a single 60-day holdout, if this needed to be more rigorous
  than "modest" scope called for.
- Persist live stream events somewhere durable (currently in-memory
  only — a server restart loses the rolling window).
- The dbt-duckdb path-resolution gotcha (profiles.yml resolves paths
  relative to the invoking shell's cwd, not the project dir) cost real
  debugging time once — worth automating around (a wrapper script) if
  this pattern recurs on a future project.

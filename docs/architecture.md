# Architecture

Covers the data platform through Phase 8 (generation → DuckDB + dbt →
Streamlit → forecasting).

## System diagram

```mermaid
flowchart TD
    seed["data/seed/*.csv\n(hand-authored)"] --> load["scripts/load_raw_data.py"]
    gen["scripts/generate_data.py\n(restaurant_ops.generation, seeded)"] --> raw["data/raw/*.csv"]
    raw --> load
    load --> rawschema[("DuckDB: raw schema")]
    rawschema --> staging["dbt: staging (views)"]
    staging --> intermediate["dbt: intermediate (views)"]
    intermediate --> facts["dbt: dimensions + facts"]
    facts --> marts[("dbt: 7 marts")]
    marts --> app["Streamlit app\n(8 pages, app/)"]
    marts --> forecasting["restaurant_ops.forecasting"]
    facts --> forecasting
    forecasting --> app

    style rawschema fill:#e1e0d9,stroke:#898781
    style marts fill:#e1e0d9,stroke:#898781
```

The ASCII version below carries the same flow with more per-layer detail
(table/model names); this diagram is the at-a-glance version.

## Data flow

```
data/seed/*.csv (hand-authored)  ─┐
                                   ├─► scripts/load_raw_data.py ─► DuckDB: raw schema
data/raw/*.csv (generated)  ──────┘         (+ loaded_at, source_file,
     ▲                                        batch_id, record_hash)
     │                                              │
scripts/generate_data.py                            ▼
(restaurant_ops.generation,                   dbt: staging (views)
 seeded, reproducible)                              │
                                                     ▼
                                            dbt: intermediate (views)
                                          reusable business logic —
                                       food cost, hourly demand, labour
                                        cost by daypart, ingredient
                                       consumption, review-to-order joins
                                                     │
                                                     ▼
                                         dbt: dimensions + facts (tables)
                                        dim_date, dim_menu_item, dim_ingredient,
                                        dim_employee, dim_supplier, dim_channel
                                        fact_orders, fact_order_items,
                                        fact_employee_shifts, fact_reviews,
                                        fact_inventory_movements
                                                     │
                                                     ▼
                                            dbt: marts (tables)
                                    mart_daily_performance, mart_menu_engineering,
                                  mart_channel_profitability, mart_labour_productivity,
                                   mart_service_quality, mart_inventory_risk,
                                              mart_review_analysis
                                                     │
                                                     ▼
                                        Streamlit application (`app/`)
```

Two independent producers feed the raw layer: `data/seed/*.csv` is
hand-authored and rarely changes (menu, ingredients, suppliers, recipes,
employees); `data/raw/*.csv` is generated fresh by
`scripts/generate_data.py` every run, from a seeded
`numpy.random.Generator` threaded through daily-context, staffing,
orders/order-items, reviews, and inventory generation in that fixed
order (see `docs/business_rules.md`).

## Layer responsibilities

- **Raw** (`raw` schema): source fields with minimal modification, plus
  load metadata. `scripts/load_raw_data.py` computes `record_hash` from
  the *original* columns only (before metadata is added), so it reflects
  content, not when/how a row was loaded.
- **Staging** (`staging` schema, views): one model per raw table.
  Renames for consistency, casts types (raw timestamps/dates arrive as
  `VARCHAR` — pandas doesn't parse dates on `read_csv` without being
  told to, and the raw layer is deliberately not the place to fix that),
  standardises text/booleans, converts empty strings to null.
- **Intermediate** (`intermediate` schema, views): reusable business
  logic that more than one downstream model would otherwise have to
  repeat — order-level profitability, menu-item food cost (recomputed
  independently in SQL from `stg_recipes` x `stg_ingredients`, rather
  than trusting the Python-computed column blindly), hourly kitchen
  demand, labour cost by date/daypart, ingredient consumption, and the
  review-to-order join.
- **Dimensions and facts** (`main` schema, tables): the star schema.
  Facts are built from intermediate models (not straight from staging)
  where reusable logic exists, so the fact tables carry finished,
  documented figures. Every fact's grain is stated at the top of its
  `.sql` file.
- **Marts** (`marts` schema, tables): one mart roughly per Streamlit
  page (see `docs/data_dictionary.md` isn't extended for these yet —
  each mart's grain and column meanings are documented as dbt model/column
  descriptions instead; run `dbt docs generate && dbt docs serve
  --project-dir dbt_restaurant` to browse them, rather than maintaining
  a second copy of the same documentation by hand).

## Why DuckDB

Single-file, zero-configuration, embedded analytical database — no
server process, no credentials, nothing else to install or run. For a
project sized at ~40k orders/~90k order items/~170k total rows, an
in-process OLAP engine with native columnar execution and first-class
pandas/CSV interop is a better fit than standing up Postgres, and it's
what `dbt-duckdb` was built for. The whole database is one file
(`data/database/restaurant.duckdb`, gitignored, fully reproducible from
`scripts/generate_data.py` + `scripts/load_raw_data.py` + `dbt build`).

## Why dbt

The project's own spec requires layered SQL transformations (staging →
intermediate → dimensions/facts → marts), documented grains, and
schema/data tests — that's dbt's exact purpose, and doing it by hand in
raw Python/SQL would mean reinventing dependency resolution (`ref()`),
testing, and documentation generation that dbt already provides.
`dbt-duckdb` needed no extra setup beyond the two config files below.

## Configuration notes worth knowing

- **`dbt-duckdb` resolves `profiles.yml`'s `path` relative to the shell's
  current working directory at invocation time, not the project
  directory.** `dbt_restaurant/profiles.yml.example` assumes dbt is
  always invoked from the repository root — see the comment in that file.
- **Schema naming**: `dbt_restaurant/macros/generate_schema_name.sql`
  overrides dbt's default behaviour, which prefixes every custom schema
  with the target schema (e.g. `main_staging`). Without that override,
  every layer's schema name would double up; with it, they're just
  `staging`, `intermediate`, `main` (dimensions/facts), and `marts`.
- **`seeds/channel_reference.csv`**: channel metadata (label, delivery
  flag, commission rate) is a dbt seed rather than derived from
  generated data, since it's fixed reference information the generator
  doesn't produce. Its `commission_rate` values are hand-kept in sync
  with `config/simulation.yaml`'s channel commission rates — a small,
  deliberate duplication documented here so it doesn't go stale
  silently.

## Streamlit application (`app/`)

`app/Home.py` is the entrypoint (`uv run streamlit run app/Home.py`);
`app/pages/1_Executive_Overview.py` through `7_Customer_Experience.py`
are auto-discovered by Streamlit's multipage convention. `app/components/`
holds everything shared across pages: `database.py` (a cached read-only
DuckDB connection plus query functions), `filters.py` (sidebar filter
widgets and formatting helpers), `charts.py` (Plotly styling/palette),
and `insights.py` (pure, UI-free functions that generate the short
natural-language summaries on Page 1).

Every page reads from the dbt-built warehouse, never the raw CSVs. Most
pages read a single mart via `database.load_mart(name)` — that covers
everything except three spec requirements that need finer grain than any
mart carries:

- Page 2's per-item drill-down (channel/hour/temperature-group demand
  for a selected menu item)
- Page 4's hourly-by-weekday heatmap
- Page 1's auto-summary, which compares actual prep time against
  `fact_orders.promised_minutes`

For those, the app queries `main.fact_orders`, `main.fact_order_items`,
`main.dim_date`, and `intermediate.int_hourly_demand` directly —
still dbt-built DuckDB tables, just outside the `marts` schema. This was
a deliberate scope decision (querying the existing fact/dim layer from
the app) rather than reopening the dbt layer to add the missing grain as
new marts.

Each `app/pages/*.py` file inserts its own directory onto `sys.path`
before importing from `components` (`sys.path.insert(0,
str(Path(__file__).resolve().parents[1]))`) rather than relying on
Streamlit's multipage import behaviour, since that behaviour isn't
guaranteed to add the same directory to the path for `Home.py` and for
scripts under `pages/`.

## Forecasting (`src/restaurant_ops/forecasting/`)

A separate package, mirroring the `generation`/`validation` module
pattern, rather than app-embedded logic — keeps the modelling code
directly unit-testable without a running warehouse or Streamlit process.

- `features.py` — turns `mart_daily_performance` into a model-ready
  frame (day-of-week/month, weather, lag/rolling order-count features).
  Pure function, no I/O.
- `evaluation.py` — chronological train/test splitting and MAE/RMSE/MAPE.
- `models.py` — the four candidate models (naive, moving average, linear
  regression, random forest) behind a shared `fit(train).predict(df)`
  interface, so the Streamlit page and evaluation loop treat them
  uniformly.
- `staffing.py` — translates a predicted order count into a recommended
  Kitchen/Front of House headcount, entirely from observed
  `mart_labour_productivity`/`fact_employee_shifts` data.
- `future.py` — the recursive 7-day-ahead forecast, reusing
  `restaurant_ops.generation.weather.generate_daily_context` to produce
  synthetic weather/calendar features for the days beyond the historical
  dataset's end.

`app/pages/8_Demand_Forecast.py` is a thin consumer of this package: it
loads `mart_daily_performance`/`mart_labour_productivity` plus
`fact_employee_shifts` (via a new `database.load_employee_shifts()`,
following the same fact-table-access pattern as Phase 7's drill-downs),
runs the pipeline once behind `st.cache_data`, and displays the results.
See `docs/business_rules.md` for the exact feature list, split, and
staffing formula.

## Live order stream (`src/restaurant_ops/streaming/`, `realtime/`)

A second, complementary showcase surface, additive to everything above
and not a replacement for the batch pipeline or the Streamlit app —
Streamlit stays the batch/historical BI tool; this is real-time. Not
part of the original `instruction.pdf` spec; see `PROGRESS.md`'s session
log for when/why it was added.

- `streaming/events.py` — `OrderEvent`, a deliberately simpler schema
  than the batch `Order`/`OrderItem` pair (event *flow*, not re-derived
  food cost/inventory/staffing).
- `streaming/simulator.py` — `LiveOrderSimulator` generates arrivals as a
  non-homogeneous Poisson process (standard thinning algorithm) whose
  rate function reuses the *same* `config/business_rules.yaml` shape the
  batch generator uses (`dayparts.*`, `demand.weekday_multipliers`,
  `demand.daypart_share`, `demand.items_per_order_weights`) — the live
  feed's rhythm resembles the historical dataset's, not a separately
  invented one. The pure core (`generate_events`) never sleeps and is
  fully unit-tested; `stream()` is a thin async wrapper adding real
  (time-scaled) pacing on top, used only by the live app.
- `streaming/aggregator.py` — `RollingWindowAggregator`, a deque-based
  sliding-window KPI rollup (order count, revenue, items/order, orders
  by channel). This is the "real-time processing" layer — plain Python,
  no external stream-processing framework, proportionate to the actual
  event volume. Always trailing 15 minutes — correct for its job, but
  not enough for a full-session view.
- `streaming/session.py` — `SessionHistory` (a capped `deque(maxlen=500)`
  of every `OrderEvent` since start — a demo process, not a service
  meant to run indefinitely) and `compute_session_summary()`, a pure
  function over that history (total orders/revenue, busiest channel,
  orders by channel, peak orders in any single minute, session
  duration). The companion to `aggregator.py` for pages that need the
  fuller session rather than a rolling snapshot.
- `realtime/main.py` — a FastAPI app mirroring `app/`'s role as a thin
  consumer: `GET /api/live/summary` (rolling-window REST snapshot),
  `GET /api/live/history` (capped session event list), `GET
  /api/live/session-summary` (`compute_session_summary()` result), and
  `websocket /ws/orders` (pushes the current rolling-window snapshot on
  connect, then every new event as it's produced). Runs the simulator as
  a background `asyncio` task at startup, starting the simulated clock
  at `simulator.default_start_time()` — 30 minutes into today's lunch
  window, not `datetime.now()` — so a freshly started demo produces
  orders almost immediately regardless of what real wall-clock time the
  server happens to start at (the arrival-rate function only depends on
  the simulated clock, so this has no downside). That same `start_time`
  value is computed once and reused as `session_start` for
  `SessionHistory`, for the same reason: session duration has to be
  measured in the same clock the event timestamps use.

No message broker (Kafka/Redis) — a deliberate scope decision for a
showcase project at this event volume; WebSockets carry the stream
directly.

## React frontend (`frontend/`)

Consumes `realtime/main.py`'s feed — a separate Vite + React +
TypeScript project, independent of the Python/uv toolchain, living
alongside `app/` (Streamlit) rather than replacing it. A multi-page app
(`react-router-dom`), built on data Streamlit doesn't have — live and
session state — not a duplicate of the historical marts. Component
library: plain Tailwind CSS + `recharts` for the chart, not Tremor —
Tremor's stable release (`@tremor/react` 3.x) requires React ^18 and a
Tailwind v3-era config, both incompatible with this project's React 19 +
Tailwind v4; its own v4-compatible line was still beta at build time.
`recharts` is the library Tremor itself is built on, so the fallback is
the same visual family without the version conflict.

Four pages, navigated via `src/components/Nav.tsx` (`main.tsx` wraps
`<App>` in `<BrowserRouter>`; `App.tsx` is the layout — `Nav` +
`<Routes>` — not a page body itself):

- `pages/LiveOperations.tsx` — KPI tiles, a live orders-per-minute
  chart, a channel breakdown, and a scrolling order feed, pushed over
  `/ws/orders`. The original single-page view.
- `pages/OrderHistory.tsx` — a sortable/filterable table of every order
  seen this session (not just the scrolling feed's last ~30), backed by
  `GET /api/live/history`. Sort/filter logic lives in
  `src/lib/historyTable.ts` (pure, unit-tested), not inlined in the
  component.
- `pages/SessionAnalytics.tsx` — cumulative stats since the server
  started (total orders/revenue, busiest channel, peak orders/minute,
  session duration), backed by `GET /api/live/session-summary` —
  distinct from Live Operations' rolling 15-minute window. Reuses
  `ChannelBreakdown`, already generic over `orders_by_channel`.
- `pages/About.tsx` — static content on the Poisson-process simulator
  and the no-message-broker decision, drawn from
  `docs/project_decisions.md`. No data fetching.

Supporting modules:

- `src/lib/types.ts` — TypeScript types mirroring `realtime/main.py`'s
  JSON shapes exactly (`OrderEvent`, `LiveSummary`, `SessionSummary`,
  the two WebSocket message variants) — hand-kept in sync, same
  trade-off already accepted for `dim_channel`'s commission rates.
- `src/lib/websocket.ts` — a typed WebSocket client with reconnect-with-
  backoff, isolated from React so it's unit-testable without mounting a
  component (`websocket.test.ts` uses a minimal mock `WebSocket`).
  Defaults to `ws://127.0.0.1:8000/ws/orders`, not `localhost` — the
  documented run command (`uv run uvicorn realtime.main:app --reload`,
  no `--host`) binds to `127.0.0.1` only, and on hosts where `localhost`
  resolves to `::1` first, a client targeting `localhost` hangs against
  a socket nothing is listening on (a permanent "Reconnecting…" state).
  Overridable via `VITE_WS_URL`. `src/lib/api.ts` applies the same
  reasoning to the REST base URL (`VITE_API_BASE_URL`).
- `src/lib/palette.ts` — the same validated categorical hex order as
  `app/components/charts.py`'s `CATEGORICAL`, so channel colors match
  between the Streamlit dashboard and this app.
- `src/lib/buckets.ts` — buckets incoming events into per-minute counts
  for the live chart. Pure, unit-tested — and the tests specifically
  cover a real subtlety: event timestamps are the simulator's own
  *simulated* clock (compressed via `time_scale`), not real wall-clock
  time, so the trailing window has to anchor to the latest event's own
  timestamp, never to the browser's `Date.now()`.
- `src/hooks/useLiveOrders.ts` — wires the WebSocket + `buckets.ts` into
  React (connection status, rolling feed, summary, chart buckets); owned
  by `App.tsx` and passed down, so the connection persists across page
  navigation and `Nav` can show status app-wide.
- `src/hooks/useSessionData.ts` — polls `/api/live/history` and
  `/api/live/session-summary` every ~5s, deliberately separate from the
  WebSocket path since Order History/Session Analytics aren't the
  primary live-updating view — keeps the WS message contract untouched.
- `src/components/` — `KpiCard`, `ChannelBreakdown`, `LiveChart`,
  `OrderFeed`, `ConnectionBadge`, `Nav`. `App.tsx` composes the layout
  plus a synthetic-data disclaimer banner, matching the convention
  already established on `app/Home.py`.

CI runs a second, parallel job (`.github/workflows/ci.yml`) for this
project — `npm ci`, lint (`oxlint`), `npm run test` (Vitest), `npm run
build` — independent of the Python job.

Self-hosted deployment (Caddy reverse proxy in front of both this app
and Streamlit, on the user's own domain) is the next and final piece —
see `PROGRESS.md` for the planned shape.

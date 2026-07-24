# Project decisions

A curated "why," not a duplicate of `docs/architecture.md` (how the
pieces fit) or `docs/development_log.md` (the blow-by-blow bug history).
This is the short version an interviewer would actually want: the real
trade-offs, what was considered and rejected, and why.

## Why synthetic data, and why this much effort on realism

The brief called for a synthetic dataset, but "synthetic" was treated as
a floor, not a ceiling: every required relationship (kitchen load → prep
time → missing items → refunds → ratings; weather/weekday → demand;
staffing → service performance) had to be *directionally real*, not just
schema-valid. Early on, a full year of data passed every validation
check yet quietly contradicted two required relationships (delivery
wasn't later than dine-in; prep time barely moved with load) — see
`docs/development_log.md` (2026-07-22 (3)). The fix wasn't a code bug,
it was a tuning problem: the constants made the effect real but
invisible. That became a standing habit for the rest of the build: after
implementing a required relationship, query the generated data grouped
by the relevant dimension and check the actual direction/magnitude —
passing validation is necessary, not sufficient, for a simulation.

## Why DuckDB, not Postgres

At ~170k total rows, an embedded, single-file, zero-server OLAP engine
with native columnar execution and first-class pandas/CSV interop is a
better fit than running a Postgres instance nobody but this project
needs. It's also exactly what `dbt-duckdb` was built for, so dbt needed
no infrastructure beyond two config files. See `docs/architecture.md`
("Why DuckDB").

## Why dbt, not hand-rolled Python/SQL transforms

The spec required layered transformations (staging → intermediate →
dimensions/facts → marts) with documented grains and schema/data tests.
Building that by hand means reinventing dependency resolution, testing,
and documentation generation dbt already provides for free. The real
payoff showed up in a concrete bug: `mart_channel_profitability` once
reported gross profit 600x too large from an unintentional join
fan-out (`docs/development_log.md`, 2026-07-22 (6)) — dbt's test
framework and documented grains made that class of bug checkable
systematically (audit every mart for the same join pattern) rather than
just fixed once and hoped not to recur elsewhere.

## Why Streamlit for the dashboard

Seven (later eight) pages of exploratory analytics reading from a
warehouse is exactly Streamlit's use case — a full page in ~100-150
lines of Python, cached DuckDB reads, no separate frontend build step.
The trade-off: Streamlit isn't built for real-time push updates, which
is why the later real-time work (below) is a *separate* app, not a
retrofit.

## Why the app reads a few fact/dim tables directly, not only marts

Two spec requirements — Menu Engineering's per-item drill-down (demand
by hour/temperature/channel) and Service Performance's hourly-by-weekday
heatmap — need finer grain than any of the 7 marts carry. The choice was
between reopening the dbt layer to add that grain as new marts, or
having the app query the underlying `fact_orders`/`fact_order_items`/
`intermediate.int_hourly_demand` directly (still dbt-built tables, never
raw CSVs). Chose the latter: it's a smaller, additive change, and three
narrow exceptions are easier to reason about than growing the mart layer
for features only one page needs. Documented explicitly in
`docs/architecture.md` so it reads as a decision, not an inconsistency.

## Why time-based validation for forecasting (and why 4 models, not 1)

The spec's forecasting requirement was explicit: never randomly split
time-series data. A 60-day chronological holdout is standard practice
and prevents a model from implicitly "seeing the future" via nearby
days leaking into training. Comparing naive/moving-average baselines
alongside linear regression and a random forest — rather than shipping
just one model — makes the regression models' actual lift visible
(MAE ~8.6-9.0 vs. ~10.6-14.5 for the baselines) instead of asserting it.
The honest caveat is in `docs/limitations.md`: this forecast is
unusually fittable *because* it's validated against the same
deterministic process that generated it, which demonstrates the
approach, not real-world forecasting accuracy.

## Why a second app (FastAPI + WebSockets) for real-time, not one bigger app

Requested afterward as a second showcase: real-time order events and,
eventually, a React frontend. Two decisions worth calling out:
- **Kept Streamlit as-is** rather than rebuilding it in React — the
  batch dashboard is finished, working, spec-complete; folding it into
  a real-time rebuild would mean re-doing shipped work instead of adding
  new work.
- **No message broker.** At this event volume, Kafka/Redis would add
  real infrastructure (a broker to install, run, and document) for no
  benefit a WebSocket doesn't already provide. The live simulator's
  arrival-rate model deliberately reuses the *same*
  `config/business_rules.yaml` weekday/daypart shape the batch generator
  uses, via a proper non-homogeneous Poisson process (thinning
  algorithm) — so the "why" here is consistency (one demand model, two
  consumption modes), not novelty for its own sake.

## A recurring theme: unit tests passing isn't the same as it working

Three separate incidents, across three different phases, shared the
same root lesson: a passing test suite doesn't prove the *real* data
shape/state matches what the code assumes.
- A dashboard KPI once showed a per-unit price next to a total cost —
  caught by looking at the *rendered* numbers next to each other in a
  screenshot, not by reading the SQL or Python in isolation
  (`docs/development_log.md`, 2026-07-24 (8)).
- The local DuckDB file silently held a 14-day dataset instead of the
  full year twice, because `pytest`'s own integration test regenerates a
  small dataset as a side effect — every mart looked "broken" while the
  code was fine (2026-07-24 (9)).
- A recursive forecast function crashed on a column-count mismatch the
  unit tests never exercised, because the test fixture happened to
  already be the right shape (`PROGRESS.md`, Session 6).

The practice this led to: after any UI or pipeline change, actually run
it — a real headless-browser screenshot for Streamlit pages, a real
`curl`/WebSocket check for the API — rather than trusting that green
tests mean the feature works.

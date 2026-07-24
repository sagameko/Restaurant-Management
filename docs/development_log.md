# Development log

Meaningful development decisions and problems encountered while building
the platform, in the format recommended by the project spec.

## 2026-07-22

Problem:
`MenuItem.model_validate` raised a `ValidationError` on `source_url` even
though the CSV loader replaced missing cells with `None` via
`df.where(pd.notnull(df), None)`.

Cause:
`pandas.read_csv(..., dtype=str)` on pandas >= 3.0 produces columns backed
by the new `StringDtype`, not plain `object`. Assigning `None` into a
`StringDtype` column via `.where` silently keeps the missing value as
`NaN` (a Python `float`) instead of `None`, so Pydantic saw a float where
`str | None` was expected.

Resolution:
Cast the DataFrame to `object` dtype (`.astype(object)`) before calling
`.where(pd.notnull(df), None)` in `restaurant_ops.ingestion.loader._read_seed_csv`.
This forces missing cells to become real `None` values that Pydantic
accepts for optional fields.

Lesson:
Don't assume `dtype=str` in pandas behaves like plain Python strings —
on pandas 3.x it opts into `StringDtype`, which has different null
semantics. Cast to `object` explicitly whenever downstream code
(here, Pydantic validation) needs `None` rather than pandas' native NA
marker.

## 2026-07-22 (2)

Problem:
`restaurant_ops.generation.orders._daily_order_count` raised
`KeyError: nan` when looking up `promotions_by_name[promotion_name]`,
even though `promotion_name` is `None` on days with no scheduled
promotion.

Cause:
`daily_context.promotion_name` was built from a list of row dicts where
most rows set the key to Python `None`. `pandas.DataFrame(list_of_dicts)`
silently converts `None` to `NaN` (a float) when inferring an object
column's dtype, so `promotion_name is not None` was always true — the
value was `nan`, not `None`.

Resolution:
Replaced every `is not None` / `is None` check against a value read out
of a DataFrame row with `pd.notna()` / `pd.isna()` in
`restaurant_ops/generation/orders.py`, which correctly treats pandas'
`NaN` as missing regardless of whether the DataFrame constructor decided
to represent "no value" as `None`, `NaN`, or `pd.NaT`.

Lesson:
This is the second time in this project a pandas-vs-Python `None`
mismatch has caused a bug (see the entry above). The pattern now: never
compare a value pulled from a pandas Series/DataFrame to `None` directly
— always use `pd.isna()`/`pd.notna()`, since pandas may have silently
turned that `None` into `NaN` or `NaT` during construction.

## 2026-07-22 (3)

Problem:
The first full-year generation run technically passed all validation
checks, but the actual data contradicted two of the spec's required
relationships: delivery channels were *less* often late than dine-in
(opposite of "delivery platforms should show a higher probability of
late complaints"), and `preparation_minutes` barely varied with
`kitchen_load_ratio` (correlation ~0.06), so "prep time should visibly
increase during high-load periods" wasn't really demonstrated.

Cause:
Two separate tuning issues in `config/business_rules.yaml`. First,
`channels.promised_minutes` for pickup/dine-in (15/18 min) was tighter
than typical kitchen prep time (~18 min average), while delivery's
32-minute promise only had to cover kitchen time (no transit leg was
modelled), so delivery was structurally almost never late. Second,
`kitchen_capacity.capacity_per_kitchen_staff_per_hour` (5.5) combined
with the roster sizes meant `estimated_kitchen_capacity` comfortably
exceeded typical hourly order volume, so `kitchen_load_ratio` rarely
exceeded 1.0 — the threshold above which the load penalty even applies.

Resolution:
Added a notional `delivery_transit_minutes` (mean 14, std 5) that's
added to `preparation_minutes` only when deciding `late_flag` for
`uber_eats`/`doordash` orders (not stored as its own column — it doesn't
apply to dine_in/pickup). Loosened dine-in/pickup promised windows to
24/23 minutes and raised delivery's to 38. Raised
`load_penalty_prep_slope` from 0.35 to 1.0 and lowered
`capacity_per_kitchen_staff_per_hour` from 5.5 to 4.5 so genuine
peak-hour order clusters exceed capacity. Re-ran and confirmed
directionally: preparation_minutes now rises from ~17.8 to ~37 minutes
across load buckets, missing-item rate 2.3%->6.9%, refund rate 4.3%->12.1%,
average rating 4.54->4.00, and delivery late rate (~29-30%) now exceeds
dine-in (~25%).

Lesson:
Passing schema/referential-integrity validation is necessary but not
sufficient for a simulation — it doesn't catch "the formula is
structurally right but the constants make the effect invisible in
practice." After building a generator with explicit required
relationships (spec section 12), actually query the generated data
grouped by the relevant dimension (load bucket, channel) and check the
direction and magnitude, not just that it ran without errors.

## 2026-07-22 (4)

Problem:
`restaurant_ops.validation.rules.validate_inventory_movements` reported
7 rows where the recomputed running inventory balance went negative, on
an ingredient that never actually ran out during the simulation itself
(`_IngredientLedger.apply` floors `on_hand` at 0 internally, so it never
went negative in the generator's own state).

Cause:
Within a business date, `generate_inventory_movements` correctly applies
a pending delivery *before* that day's consumption in the simulation
loop — but the delivery's movement row was timestamped `hour=7` while
consumption defaulted to `hour=6`. The validator recomputes the running
balance by sorting on `movement_timestamp`, so it saw that day's
consumption at an *earlier* timestamp than the delivery that (in
reality, per the simulation's own processing order) arrived first —
making a perfectly fine ledger look like it went negative.

Resolution:
Made every movement type's hour-of-day explicit and consistent with true
processing order: `Stock Adjustment` (initial stocktake) at hour 0,
`Supplier Delivery` (scheduled and emergency) at hours 6-7, `Sales
Consumption` at hour 20, `Waste` at hour 21, `Expired Stock` at hour 22,
`Stock Adjustment` (stocktake correction) at hour 23. Removed the
function's `hour: int = 6` default so every call site has to state its
hour explicitly, rather than silently inheriting a default that happened
to be wrong for most call sites.

Lesson:
When a validator recomputes state by sorting on a timestamp column,
that column has to reflect true causal order, not just "same calendar
day." A daily-aggregated movement (consumption) and an early-morning
event (delivery) landing on the same `business_date` isn't enough — get
the hour-of-day right too, or a correct simulation will look broken to
anything that re-derives state from the recorded events instead of
trusting the generator's internal (correct) bookkeeping.

## 2026-07-22 (5)

Problem:
After Phase 4 added real employee shifts, the first full-year run showed
`total labour_cost / total net_sales = 86%` — combined with the existing
~14.5% food cost, that's over 100% of revenue on food and labour alone,
before rent, utilities, or any profit. Not "high," impossible.

Cause:
`kitchen_capacity.staff_roster` (2-7 people per shift, existing since
Phase 3) was originally sized only to keep `kitchen_load_ratio` behaving
realistically (mostly under 1.0 with periodic peaks above it) — nobody
had checked what that roster, multiplied by realistic Australian
hospitality hourly rates and shift lengths, implied for total labour
cost against this menu's actual revenue per order. It implied roughly
100 labour-hours/day for a restaurant doing ~$3,250/day in net sales.

Resolution:
Retuned `kitchen_capacity.capacity_per_kitchen_staff_per_hour` from 4.5
to 9.0 (a "more efficient kitchen" assumption) and cut the roster
roughly in half (e.g. weekday dinner kitchen 4->2, front-of-house 6->2),
choosing the new roster x new capacity products to land close to the old
per-slot capacity for several slots (weekday dinner: 2x9=18 vs old
4x4.5=18, unchanged) so `kitchen_load_ratio`'s distribution wouldn't be
disrupted. Also cut shift buffer time from 1 hour (0.5 before + 0.5
after) to 15 minutes (0.25 before, 0 after). Re-ran and confirmed:
labour cost fell to 34.7% of net sales (a realistic, if high-end,
figure for Australian hospitality), while the load-driven relationships
(prep time 17.6->43min, missing-items 2.0%->8.4%, refunds 4.1%->13.8%
across load buckets) stayed intact and clearly directional.

Lesson:
A generator constant that's tuned in isolation for one relationship
(kitchen_load_ratio's realism) can silently break an entirely different
one (labour cost as a percentage of revenue) if nobody cross-checks the
implied real-world total. After tuning any cost- or capacity-related
constant, compute the aggregate financial ratio it implies (here:
labour % of revenue, food % of revenue, combined prime cost) and check
it against a plausible real-world range — not just whether the
per-record math is internally consistent.

## 2026-07-22 (6)

Problem:
`marts.mart_channel_profitability.estimated_gross_profit` showed values
like $1.67e8-$8.1e8 per channel — hundreds of millions of dollars, when
the whole year's actual net sales across every channel totalled about
$1.2M. The model also took 6.7 seconds to build, an outlier next to
every other mart's ~0.2-0.4 seconds.

Cause:
The model joined `fact_orders` (order-grain, ~39k rows) and
`fact_reviews` (review-grain, ~8k rows) directly to `dim_channel` in the
same query, both on `channel`, then aggregated with `group by`. Neither
join condition ties a specific order to a specific review, so for each
channel dbt-duckdb computed every matching order row paired with every
matching review row on that channel before the `group by` collapsed it
— a cross-product fan-out, not a 1:1 or many:1 join. Every `sum()` over
`orders.*` columns was inflated by a factor equal to that channel's
review count (thousands), which is exactly why the numbers were roughly
6 orders of magnitude too large, and why the query was slow (it was
materializing millions of joined rows before aggregating).

Resolution:
Aggregated `fact_orders` and `fact_reviews` to channel grain in
*separate* CTEs first (each producing one row per channel), then joined
those two already-aggregated, 1-row-per-channel results together — a
safe 1:1 join with no fan-out. Checked every other mart for the same
pattern (join two un-aggregated fact-grain tables directly, then
group-by): none of the others had it, because they either joined
fact-grain data to genuinely-aggregated CTEs from the start, or joined
on an actual foreign key (like `fact_reviews.order_id ->
fact_orders.order_id` in `mart_review_analysis`, which is a real 1:1
relationship, not a shared-category-style join).

Lesson:
Never join two tables directly on a non-unique shared attribute (like
`channel`, `category`, `business_date`) when both sides have more than
one row per value of that attribute — aggregate each side to that
grain *first*, then join the aggregates. A join is only safe without
pre-aggregating when at least one side is already unique on the join
key (a real dimension, or a foreign-key relationship), or you accept
the fan-out and want it (which is rare and should be explicit, e.g. via
an intentional cross join). An unexpectedly slow model build is often a
free warning sign of an unwanted fan-out before you even check the
numbers — the row count blew out long before the wrong totals were
visible.

## 2026-07-22 (7)

Problem:
The first real GitHub Actions run of CI failed all three
`tests/integration/test_pipeline.py` tests with `Could not find profile
named 'restaurant_ops'`, even though the exact same test suite passed
locally and `dbt build` had been verified working directly moments
before pushing.

Cause:
`.github/workflows/ci.yml`'s "Configure dbt profile" step (which copies
`profiles.yml.example` to the gitignored `profiles.yml`) was ordered
*after* "Run tests" — but the integration test's `pipeline_result`
fixture invokes `dbt build` as a subprocess, which needs that file to
exist. On a fresh CI checkout there's no `profiles.yml` yet at that
point. This never reproduced locally because `dbt_restaurant/profiles.yml`
had already existed on disk since the profile-setup step earlier in
this same session — a stale local file masking a real ordering bug in
the checked-in workflow.

Resolution:
Moved "Configure dbt profile" to immediately after `uv sync`, before
lint and tests. Verified by actually deleting the local
`profiles.yml` and `restaurant.duckdb` and re-running the full sequence
in the corrected order, rather than trusting the YAML reordering alone.

Lesson:
A locally-passing test suite doesn't prove a workflow's *step order* is
correct if local state (a file created once, days of iteration ago) can
silently substitute for a step CI is supposed to perform. When a test
depends on setup a CI step is responsible for, verify by actually
removing that local state and re-running — don't just re-read the YAML
and reason about it.

## 2026-07-24 (8)

Problem:
The Streamlit dashboard's Menu Engineering item drill-down showed
"Estimated cost: $3,651" directly next to "Price: $13" for a single
item — a nonsensical per-unit price beside a four-figure "cost."

Cause:
`mart_menu_engineering.estimated_food_cost` is the item's *total* cost
summed across every unit sold in the dataset (it's built for the
menu-engineering matrix's aggregate margin calculation), but
`selling_price` is a genuine per-unit figure. The Streamlit page put both
under a KPI row without checking they shared the same grain.

Resolution:
Divided by `units_sold` to get a per-unit figure before displaying it,
and relabelled the card "Estimated cost / unit."

Lesson:
This wasn't caught by reading the mart's SQL or the Streamlit code in
isolation — both were individually correct for what they were built for.
It was only visible by actually looking at the *rendered numbers* next
to each other on the page (via a headless-browser screenshot), the same
way a human reviewer would notice "$3,651 next to $13 looks wrong" at a
glance. A column name matching between two joined-in-the-UI data sources
isn't proof they share a grain — check by looking at real rendered
output, not just by reading the query.

## 2026-07-24 (9)

Problem:
Twice in one week, a mart that should have had ~365-730 rows (one per
business date, or one per date/daypart) instead had only 14-28 rows, and
every KPI on the affected Streamlit page looked tiny and wrong at first
glance — `mart_labour_productivity` briefly showed only 28 rows while
building Phase 7's Labour Productivity page, and it recurred later in
Phase 8 with fresh screenshots suddenly showing $8,619 net sales instead
of the expected ~$1.2M.

Cause:
`data/database/restaurant.duckdb` and `data/raw/*.csv` are gitignored
and machine-local, not part of the repo's committed state. Two different
things reset them to a small 14-day dataset: a prior session's leftover
local state, and — the recurring one — `tests/integration/test_pipeline.py`
itself, which deliberately regenerates a small dataset
(`--days 14 --average-orders 20`, matching the CI job's fast smoke test)
as its own test fixture, as a side effect of simply running `uv run
pytest`.

Resolution:
Regenerated the full year
(`--start-date 2025-07-01 --days 365 --average-orders 100 --seed 42`,
reload, `dbt build`) each time before trusting any screenshot or manual
query again.

Lesson:
Local, gitignored database/data state can silently be the wrong size or
the wrong shape, and nothing about the dbt build succeeding (98/98 tests
still pass either way) will tell you that — a 14-day dataset builds just
as cleanly as a 365-day one. After running `pytest` (which exercises the
real generate → load → `dbt build` pipeline as an integration test) and
before trusting any dashboard number or screenshot, check the actual row
count/date range of the mart you're about to look at, or just
unconditionally regenerate the full dataset — don't assume yesterday's
local build is still what's on disk.

## 2026-07-25

Problem:
The live order stream (`realtime/main.py`) appeared to freeze — KPI
numbers, the live chart, and the order feed all stopped updating,
identically, for well over a minute of real time, with no errors in the
server log and every HTTP endpoint still responding normally.

Cause:
Not a crash. `LiveOrderSimulator._next_arrival` correctly finds the next
order's simulated timestamp in one step, including across the ~14
simulated-hour gap between dinner close and the next day's lunch
opening (during which the true arrival rate is exactly zero). But
`stream()` then does a single `await asyncio.sleep(real_delay_seconds)`
for that *entire* gap before yielding the event — at the default
`time_scale=60`, a 14-simulated-hour gap is a genuine ~14 *real* minute
`asyncio.sleep`. The event loop stayed responsive throughout (which is
why HTTP endpoints kept working) — only the simulator's own background
task was legitimately, correctly waiting, just for far longer than a
live demo should ever visibly pause.

Resolution:
Added `max_real_sleep_seconds` (default 20.0) to `stream()`: each wait
is `min(real_delay_seconds, max_real_sleep_seconds)`, then `sim_time`
still jumps straight to the actual next arrival regardless of how long
was actually slept. This only changes *pacing* during closed hours —
the generated event and its timestamp are identical either way — not
the demand model itself. Added
`test_stream_caps_real_sleep_across_the_overnight_gap`, which patches
`asyncio.sleep` to record call arguments and asserts none exceed the
cap — and, to prove the test isn't vacuous, confirmed via a separate
isolated script that the *uncapped* delay for this exact scenario really
is ~859 seconds, not a few seconds that happened to round down.

Lesson:
This class of bug is invisible to unit tests that only run for seconds
of simulated time (every existing test used short windows — hours, not
days — specifically because they run fast) and invisible to a short
manual smoke test too (a 15-30 second check, which is what every prior
phase's live-demo verification in this project happened to use). It
only showed up because this session's demo ran long enough, doing
other work in between, to actually cross a day boundary. The general
lesson already written elsewhere in this log — verify by actually
running the thing, not by reading the code — has a corollary: *how
long* you run it for is itself a variable worth varying, since some
bugs only exist past a duration no test or quick check happens to reach.

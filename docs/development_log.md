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

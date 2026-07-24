# Algorithms

`docs/business_rules.md` documents the formulas and config values.
`docs/project_decisions.md` documents the architectural "why this stack."
This page is the layer between them: the actual **methods** used across
the project, and why that method over the obvious alternatives — the
kind of detail worth being able to explain from memory, not just cite.

## Demand generation: multiplicative Poisson, two sampling strategies

Both the batch generator and the live stream draw from the *same*
underlying demand model — `average_daily_orders × weekday_multiplier ×
weather/holiday/event multipliers` (batch) or `× intraday_density(hour)`
(live) — but sample it two different ways, each suited to its context:

- **Batch** (`restaurant_ops.generation.orders`): for a known, fixed
  business date, draw a single Poisson-distributed total order count for
  that whole day (`np.random.poisson(mean)`), then split that count
  across dayparts/hours by weighted sampling. Efficient when you already
  know the full time window up front and just need *a* count.
- **Live** (`restaurant_ops.streaming.simulator`): there's no fixed count
  to sample — orders have to arrive one at a time, at real (or
  time-scaled) moments, as the process runs. This calls for a genuine
  point process, not a single random draw — see below.

## The live simulator: Poisson thinning, not a fixed-rate loop

A naive live simulator might do `while True: sleep(1/rate); emit_order()`
— but `rate` here isn't constant, it swings from ~0 at 3am to a sharp
peak at 7pm on a Saturday. A **homogeneous** Poisson process (constant
rate) can't represent that; you need a **non-homogeneous** one (rate
varies with time), and the standard way to sample from one without
discretizing time into buckets is **thinning** (Lewis & Shedler, 1979):

1. Find (or bound) `λ_max`, the highest the true rate ever gets.
2. Draw a candidate inter-arrival time from `Exponential(λ_max)` — fast
   to sample, and guaranteed to over-produce candidates relative to the
   true rate anywhere.
3. Accept each candidate with probability `true_rate(t) / λ_max`; reject
   and draw the next candidate otherwise.

The result is statistically exact: accepted arrivals follow the true,
time-varying rate. It also has a nice property for this project
specifically — "is the restaurant open" needs no `if` statement anywhere;
outside service hours `true_rate(t) = 0`, so the acceptance probability
is 0 and every candidate there is rejected until the clock drifts back
into an open window. See `src/restaurant_ops/streaming/simulator.py`'s
`_next_arrival` for the implementation, and `docs/business_rules.md`
for the exact rate function.

## Recursive multi-step forecasting

`forecasting.future.forecast_next_days` predicts 7 days past the end of
the historical dataset. Day 1's lag features (`previous_day_orders`,
`rolling_7day_avg`) come from real history. Day 2 onward, they can't —
that data doesn't exist yet — so the function feeds its own prior
*predictions* back in as if they were real observations. This is simply
how any multi-step time-series forecast has to work (the alternative,
holding lag features frozen at day-1 values, would silently ignore the
very trend the model is supposed to be following) — but it's easy to
get wrong by accident, which is why
`test_forecast_next_days_feeds_predictions_back_in_recursively`
(`tests/unit/test_forecasting.py`) exists as an explicit proof, not just
an assumption.

## Forecast model comparison: why these four, why time-based split

Four candidates (`restaurant_ops.forecasting.models`), deliberately
spanning a spectrum from "no learning at all" to "captures nonlinear
interactions":

| Model | What it captures | What it misses |
|---|---|---|
| Naive (previous week) | Weekly seasonality, nothing else | Trend, weather, promotions |
| Moving average (7-day) | Smooths noise | Any day-of-week structure at all |
| Linear regression | Additive effects of day-of-week, weather, lags | Interactions between features |
| Random forest | Nonlinear interactions (e.g. "Friday + rain") | Extrapolation beyond training range |

Comparing all four — rather than shipping the fanciest one — is what
makes the simpler models' shortcomings *visible* instead of asserted: on
this project's real holdout, linear regression's MAE (~8.6 orders) beats
the moving average's (~14.5) by a wide margin, exactly the gap you'd
expect once day-of-week and weather actually get modeled instead of
smoothed over. The split is strictly chronological — last 60 days held out,
never a random sample of days — because a random split lets a model
implicitly see "the future" via nearby days landing in its training set,
which silently inflates every reported metric for time-series data
specifically (see `docs/project_decisions.md` for the fuller argument).

**Three metrics, not one**, because each catches a different failure
mode: MAE is robust to outliers and easy to explain ("off by 8.6 orders
on average"); RMSE penalizes large misses more than small ones (worse if
a model is occasionally very wrong vs. consistently a little wrong);
MAPE expresses error as a percentage, comparable across differently-sized
values.

## Menu engineering: median split, not fixed thresholds

`mart_menu_engineering` classifies each item as Star/Plowhorse/Puzzle/Dog
by comparing its `units_sold` and `contribution_margin_pct` against this
menu's own **median**, not a fixed absolute number ("sells > 500 units"
would be meaningless without knowing this menu's actual scale). A median
split is also self-balancing: roughly half of items land above/below
each axis by construction, so the four categories come out comparably
sized regardless of the underlying distribution's shape — a fixed
threshold picked from one menu wouldn't transfer to another. See
`docs/business_rules.md` for the exact SQL-level definition.

## Staffing recommendation: median benchmark, not mean

`forecasting.staffing.recommend_staffing` and the live stream's session
analytics both use the **median** `orders_per_labour_hour` across
`Balanced`-flagged historical days as the productivity benchmark, not
the mean. A handful of unusually chaotic (or unusually quiet) days would
pull a mean benchmark toward their extreme; the median stays anchored to
what a "typical" balanced day actually looks like — the same reasoning
as the menu-engineering median split above, applied to a different
problem.

## Rolling-window aggregation: a deque, not a recomputation

`streaming.aggregator.RollingWindowAggregator` keeps a `deque` of recent
events and evicts from the *left* as new events push the window forward
— O(1) amortized per event, versus rescanning the full event history on
every update. At this project's event volume the difference is
invisible either way, but the pattern is the right one to reach for by
default: it's the same idea a real production rate-limiter or
sliding-window metric would use, just applied here at demo scale.

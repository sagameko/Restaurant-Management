# Business rules

Documents the modelling assumptions behind the synthetic data, as they are
implemented. Food-cost (Phase 2) and demand/channel/staffing/review
(Phase 3) rules exist so far. Inventory-reorder and menu-engineering
classification rules will be added as those phases land — see
`PROGRESS.md`. All tunable constants referenced below live in
`config/business_rules.yaml`, not in code.

## Food-cost calculation

Implemented in `restaurant_ops.ingestion.loader.compute_menu_item_food_costs`.

For each menu item, the estimated food cost is the sum, across every
recipe line for that item, of the ingredient quantity required times its
estimated unit cost, inflated by that line's estimated wastage
percentage:

```
estimated_item_food_cost
= sum(
    quantity_required
    x ingredient.estimated_unit_cost
    x (1 + estimated_wastage_pct)
)
```

`estimated_gross_profit = selling_price - estimated_item_food_cost`, and
`estimated_gross_margin_pct = estimated_gross_profit / selling_price`.

All profitability figures use the word "estimated" throughout the
platform because they are derived from synthetic ingredient costs, not
real supplier pricing.

Across the current 51-item menu the average estimated food-cost
percentage is approximately 14-15%. Real-world Vietnamese casual-dining
food cost typically runs closer to 28-35%; this dataset's recipe
quantities/wastage were set for a plausible bill-of-materials shape
(protein + carb + veg + herb + sauce lines) rather than tuned to hit a
specific food-cost target. Revisit recipe quantities or wastage
percentages in a later phase if a more realistic food-cost ratio is
wanted for the menu-engineering marts.

## Seed-data referential integrity

Enforced by `restaurant_ops.ingestion.loader.validate_referential_integrity`:

- Every `ingredients.supplier_id` must exist in `suppliers.csv`.
- Every `recipes.menu_item_id` must exist in `menu_items.csv`.
- Every `recipes.ingredient_id` must exist in `ingredients.csv`.
- Every `menu_items.menu_item_id` must have at least one `recipes.csv` row.

## Demand assumptions (order generation, Phase 3)

Implemented in `restaurant_ops.generation.orders._daily_order_count` and
`_daypart_split`. Each business date gets a target mean order count:

```
mean_orders
= average_daily_orders
  x weekday_multiplier[day_of_week]      # Fri/Sat highest, Mon/Tue lowest
  x weather_multiplier                   # cold or hot day bump, whichever applies
  x holiday_multiplier (if public holiday)
  x city_event_multiplier (if a fictional city event that day)
  x promotion_volume_multiplier (if a promotion is scheduled that day)
```

`total_orders = Poisson(mean_orders)`, then split into lunch/dinner using
a configurable dinner-share fraction that increases on weekends (dinner
skews later/bigger on Fri-Sun). Within a menu item's basket-selection
weight, `lunch_affinity`/`dinner_affinity` and
`cold_weather_affinity`/`hot_weather_affinity` (from `menu_items.csv`)
are applied multiplicatively on top of `base_popularity_weight`, which is
what produces the required patterns (lunch generates more Banh Mi/pickup,
cold days generate more Pho, hot days generate more Vermicelli
Salad/Drinks) — verified in `tests/unit/test_order_generation.py`.

## Channel assumptions

Channel probabilities (`config/simulation.yaml`) are adjusted per daypart
(lunch skews toward pickup, dinner skews toward delivery and dine-in),
then renormalised. Delivery channels (`uber_eats`, `doordash`):

- incur `platform_commission = (subtotal - discount_amount) x commission_rate`
  (zero for `dine_in`/`pickup`, and zero for any cancelled order),
- have longer `promised_minutes` (38 vs 24 for dine-in, 23 for pickup),
  but that promise has to cover a courier pickup + transit leg on top of
  kitchen prep. A random `delivery_transit_minutes` (mean 14, std 5) is
  added to `preparation_minutes` only when deciding `late_flag` for
  delivery orders — it is not itself a stored column, since it doesn't
  apply to `dine_in`/`pickup`. This is what makes delivery orders late
  more often than dine-in despite the longer promised window, per the
  spec's channel-relationship requirement.

## Staffing / kitchen-load assumptions

Implemented in `restaurant_ops.generation.staffing.generate_shifts`
(schedules real employees) and `restaurant_ops.generation.orders`
(consumes the result). For each business date x daypart,
`generate_shifts` tries to schedule a target headcount —
`config/business_rules.yaml: kitchen_capacity.staff_roster`, keyed by
(weekday vs weekend) x (lunch vs dinner) — by sampling without
replacement from the active Kitchen/Front of House employees in
`employees.csv`. Each scheduled employee independently has a chance
(`staffing.absence_probability`, 4%) of being absent that shift
(`actual_hours = 0`, `labour_cost = 0`, and they don't count toward
effective staffing). `orders.py` receives the resulting *effective*
(scheduled-minus-absent) headcount per (business date, daypart), not the
target — that's what lets employee absence actually move
`kitchen_load_ratio` day to day, per the spec's staffing-relationship
requirement.

```
estimated_kitchen_capacity = effective_kitchen_staff_count x capacity_per_kitchen_staff_per_hour
kitchen_load_ratio = orders_placed_in_the_same_hour / estimated_kitchen_capacity

preparation_minutes
= max(item_prep_minutes) + 0.4 x sum(other items' prep_minutes)   # base_prep
  scaled by (1 + load_penalty_slope x max(0, kitchen_load_ratio - 1))
  + noise
```

As `kitchen_load_ratio` rises above 1.0, `preparation_minutes` rises,
`missing_item_flag` probability rises, refund/cancellation probability
rises, and (via the review formula below) ratings fall — all four
verified directionally in `tests/unit/test_order_generation.py` against
the actual generated dataset, not just asserted structurally from the
formula.

**Why the roster looks small (2-3 people per shift) and
`capacity_per_kitchen_staff_per_hour` looks high (9.0)**: these two
constants were tuned together, not independently. An earlier pass sized
the roster around "orders per hour" alone and left total labour cost as
an afterthought — the result was a nonsensical 86% labour-cost-to-net-sales
ratio (more than a real restaurant's entire revenue, once food cost is
added in). Cutting headcount while raising per-person throughput
proportionally keeps `kitchen_load_ratio` behaving the same way (capacity
per shift is close to unchanged for several slots) while bringing labour
cost down to ~35% of net sales — high by many countries' standards, but
plausible for Australian hospitality wages (award rates + casual loading
routinely put blended labour cost in the 30s here). See the
2026-07-22 development-log entry for the numbers.

## Inventory assumptions (Phase 5)

Implemented in `restaurant_ops.generation.inventory`. One ledger per
ingredient is simulated across the whole date range, in chronological
order, tracking a running on-hand balance:

```
ingredient_consumption(business_date)
= sum over fulfilled, non-cancelled order items that day of
    order_item.quantity x recipe.quantity_required
```

Only `item_status = "Fulfilled"` lines on non-`Cancelled` orders draw
down stock — a `"Missing"` item was never actually made, and a cancelled
order's food never got made either.

`recipes.estimated_wastage_pct` (the Phase 2 food-costing assumption)
doubles as the *actual* waste-rate driver here: on a random subset of
consumption days per ingredient (`inventory.waste_probability_per_consumption_day`),
a `Waste` movement equal to roughly that day's consumption times the
larger of a random fraction or the recipe's own wastage percentage is
recorded — connecting the Phase 2 costing assumption to an actual Phase 5
simulated outcome, not just a cost multiplier.

**Reordering and emergency purchasing**: once on-hand drops below
`ingredients.reorder_level`, a normal-lead-time delivery
(`suppliers.average_lead_time_days`) is scheduled to arrive later,
brought up to a target level (`inventory.reorder_target_days_of_cover`
days of average consumption, or 2x the reorder level, whichever is
higher). Separately — and this is what actually guarantees the ledger
never goes negative — if a single day's consumption alone would exceed
current on-hand stock, a same-day emergency delivery is triggered *before*
that day's consumption is recorded, at a cost premium
(`inventory.emergency_cost_multiplier`, 1.15x). This is the spec's
"emergency purchasing" driver, made literal: a kitchen can't serve an
ingredient it doesn't have, so the simulation makes sure it always has
enough by the time it's needed, at a cost.

**Expiry**: short-shelf-life ingredients expire more often — expiry
probability per day is `inventory.expiry_base_probability_per_day` scaled
by `expiry_reference_shelf_life_days / ingredient.shelf_life_days`, so an
ingredient with a 5-day shelf life expires roughly 6x as often as the
30-day reference point.

**Stock adjustments**: a small weekly probability
(`inventory.stock_adjustment_probability_per_week`) of a random +/-
correction, representing stocktake variance.

**Movement timestamps matter for validation**: within a business date,
movements are timestamped in the order they're actually applied to the
ledger — deliveries in the morning (hour 6-7), consumption at end of
service (hour 20), then waste/expiry/adjustment after that (hours 21-23).
`restaurant_ops.validation.rules.validate_inventory_movements` recomputes
a running balance by sorting on `movement_timestamp`, so if a same-day
delivery were stamped *after* that day's consumption instead of before,
the recomputed balance would look negative even though the simulation
itself never let on-hand go below zero — see the 2026-07-22 development-log
entry for exactly this bug.

## Review-generation logic

Implemented in `restaurant_ops.generation.reviews`. Ratings are never
`random.randint(1, 5)` — they're a formula seeded at a high base and
penalised by the same operational outcomes staffing affects:

```
rating_score = 4.8
if late_flag:                                     rating_score -= 0.8
if missing_item_flag:                              rating_score -= 1.5
if preparation_minutes > promised_minutes + 10:    rating_score -= 0.5
rating_score += random_noise (std 0.35)
rating = round(clip(rating_score, 1, 5))            # nearest whole star
```

Only `Completed` and `Partially Refunded` orders are eligible for a
review (a cancelled order was never fulfilled, so there's nothing to
rate); review probability itself varies by channel (delivery apps
prompt for reviews far more than dine-in, 35% vs 12%).
`complaint_category` is `"Missing Item"` or `"Late Order"` when those
flags are set, otherwise a random category for any other rating <= 2,
otherwise `None`. `response_required_flag` is true whenever
`rating <= 2` or a complaint category was assigned. Review text is drawn
from a small set of hand-written templates keyed by rating band
(positive/neutral/negative) in `config/business_rules.yaml: reviews.templates`
— clearly synthetic, not scraped review content.

## Menu-engineering classification (dbt, Phase 6)

Implemented in `dbt_restaurant/models/marts/mart_menu_engineering.sql`.
An item's `units_sold` (from fulfilled, non-cancelled order items only)
and `contribution_margin_pct` are each compared against the **median**
across all menu items — not a fixed absolute threshold, since "good"
sales volume or margin only means anything relative to this specific
menu:

```
popularity_classification    = 'High' if units_sold >= median(units_sold) else 'Low'
profitability_classification = 'High' if contribution_margin_pct >= median(contribution_margin_pct) else 'Low'

menu_engineering_classification:
  Star      = High popularity + High profitability
  Plowhorse = High popularity + Low profitability
  Puzzle    = Low popularity + High profitability
  Dog       = Low popularity + Low profitability
```

A median split means every item is classified relative to this menu's
own middle, which is why the four categories come out roughly balanced
in practice (see `docs/development_log.md`) rather than skewed toward
one label.

## Weather and calendar assumptions

Temperature follows a synthetic seasonal cosine curve for Melbourne
(mean ~18C, amplitude ~7.5C, peak in late January) plus daily noise —
this is a model, not historical weather data (see `docs/limitations.md`).
Rain is a Bernoulli draw with a season-dependent probability, and when it
rains, `rain_mm` is drawn from an exponential distribution. Public
holiday dates are *computed*, not hardcoded per year (Easter via the
Anonymous Gregorian algorithm; Labour Day/King's Birthday/Melbourne Cup
via n-th-weekday-of-month rules) — see
`restaurant_ops.generation.weather.victorian_public_holidays`. These are
real Victorian public holiday rules, not synthetic data. City events are
fictional, recurring on the same month/day every simulated year.

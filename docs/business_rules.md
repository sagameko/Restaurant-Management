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

## Staffing / kitchen-load assumptions (Phase 3 placeholder)

`kitchen_staff_count` and `front_of_house_staff_count` come from a fixed
roster table keyed by (weekday vs weekend) x (lunch vs dinner) —
`config/business_rules.yaml: kitchen_capacity.staff_roster` — **not**
from real employee/shift data, since Phase 4 doesn't exist yet.

```
estimated_kitchen_capacity = kitchen_staff_count x capacity_per_kitchen_staff_per_hour
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

**Revisit in Phase 4**: once `fact_employee_shifts` exists, replace the
fixed roster with real scheduled/actual staff counts per shift, and
recompute `kitchen_load_ratio`/`preparation_minutes` from that instead.

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

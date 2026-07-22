# Data dictionary

Documents every table as it is implemented. The seed layer (Phase 1/2)
and the daily-context/orders/order-items/reviews generated tables
(Phase 3) exist so far; employee shifts and inventory movements will be
added here once Phase 4/5 land.

## Seed tables (`data/seed/`)

All seed tables are manually maintained CSVs, hand-authored for this
project. Menu item names, categories and prices are an illustrative,
representative Vietnamese menu — synthetic, not scraped from any live
source. All costs, suppliers and recipe quantities are synthetic
estimates.

### `menu_items.csv`

- **Purpose**: the sellable menu, and the attributes that drive synthetic
  demand generation in later phases (weather/daypart/delivery affinities).
- **Grain**: one row per menu item.
- **Primary key**: `menu_item_id`.
- **Foreign keys**: none.
- **Synthetic/public-source status**: `source_type` column, currently
  `synthetic` for every row.

| Column | Description |
|---|---|
| `menu_item_id` | Unique item identifier, e.g. `MI014`. |
| `item_name` | Display name. |
| `category` | One of 11 menu categories (Starters, Dumplings, Rice Paper Rolls, Banh Mi, Pho Noodles, Pho Xao, Rice Bowls, Vermicelli Salad, Sharing Plates, Sides, Drinks). |
| `selling_price` | Menu price in AUD. |
| `estimated_prep_minutes` | Expected kitchen prep time at normal load. |
| `vegetarian` / `vegan` / `gluten_free` | Dietary flags. |
| `available_for_delivery` | Whether the item is offered on delivery channels. |
| `base_popularity_weight` | Relative demand weight used by the order generator (Phase 3). |
| `cold_weather_affinity` / `hot_weather_affinity` | Multiplier applied to demand based on temperature (Phase 3). |
| `lunch_affinity` / `dinner_affinity` | Multiplier applied to demand based on daypart (Phase 3). |
| `delivery_affinity` | Multiplier applied to demand for delivery channels (Phase 3). |
| `source_type` | `synthetic` or `public_source`. |
| `source_url` | Populated only when `source_type = public_source`. |

### `ingredients.csv`

- **Purpose**: the ingredient master used for recipe costing and, in
  Phase 5, inventory simulation.
- **Grain**: one row per ingredient.
- **Primary key**: `ingredient_id`.
- **Foreign keys**: `supplier_id` -> `suppliers.supplier_id`.
- **Synthetic/public-source status**: entirely synthetic (`synthetic_estimate = true` for every row).

| Column | Description |
|---|---|
| `ingredient_id` | Unique ingredient identifier, e.g. `ING014`. |
| `ingredient_name` | Ingredient name. |
| `ingredient_category` | e.g. Protein, Produce, Herb, Condiment, Stock, Pantry, Bakery, Dairy, Beverage, Seafood, Grain, Noodles, Wrapper. |
| `unit` | One of `kilograms`, `litres`, `each`, `portions`. |
| `estimated_unit_cost` | Synthetic cost per unit, in AUD. |
| `shelf_life_days` | Used for waste/expiry simulation (Phase 5). |
| `reorder_level` | Stock level that triggers a reorder signal (Phase 5). |
| `safety_stock` | Minimum buffer stock (Phase 5). |
| `supplier_id` | The primary supplier for this ingredient. |
| `synthetic_estimate` | Always `true` in this dataset. |

### `suppliers.csv`

- **Purpose**: supplier master, used for inventory delivery simulation
  (Phase 5) and referenced by `ingredients.supplier_id`.
- **Grain**: one row per supplier.
- **Primary key**: `supplier_id`.
- **Foreign keys**: none.
- **Synthetic/public-source status**: entirely synthetic.

| Column | Description |
|---|---|
| `supplier_id` | Unique supplier identifier, e.g. `S02`. |
| `supplier_name` | Synthetic supplier name. |
| `supplier_category` | Produce & Herbs, Meat & Poultry, Seafood, Dry Goods & Pantry, Bakery, or Beverages. |
| `average_lead_time_days` | Typical delivery lead time, used in Phase 5 supplier-delivery simulation. |
| `reliability_score` | 0-1 synthetic reliability score, used to vary delivery timing/quality in Phase 5. |
| `synthetic_estimate` | Always `true`. |

### `recipes.csv`

- **Purpose**: bill-of-materials linking each menu item to the ingredients
  and quantities required to produce one serving. Drives estimated food
  cost (Phase 2) and ingredient consumption (Phase 5).
- **Grain**: one row per (menu item, ingredient) pair.
- **Primary key**: composite (`menu_item_id`, `ingredient_id`).
- **Foreign keys**: `menu_item_id` -> `menu_items.menu_item_id`;
  `ingredient_id` -> `ingredients.ingredient_id`.
- **Synthetic/public-source status**: entirely synthetic.

| Column | Description |
|---|---|
| `menu_item_id` | The menu item this recipe line belongs to. |
| `ingredient_id` | The ingredient consumed. |
| `quantity_required` | Quantity of `unit` consumed per serving. |
| `unit` | Must match the ingredient's own unit of measure. |
| `estimated_wastage_pct` | Fractional wastage applied on top of the raw quantity when costing (e.g. `0.05` = 5%). |

Every menu item has at least one recipe row, and every recipe row
references a real menu item and ingredient — enforced by
`restaurant_ops.ingestion.loader.validate_referential_integrity` and
covered by `tests/unit/test_recipe_costs.py`.

### `employees.csv`

- **Purpose**: the staff roster `restaurant_ops.generation.staffing`
  schedules real shifts against.
- **Grain**: one row per employee.
- **Primary key**: `employee_id`.
- **Foreign keys**: none.
- **Synthetic/public-source status**: entirely synthetic — names, roles
  and rates are all fictional/illustrative.

| Column | Description |
|---|---|
| `employee_id` | Unique employee identifier, e.g. `E07`. |
| `employee_name` | Synthetic name. |
| `department` | `Kitchen` or `Front of House`. |
| `role` | e.g. Head Chef, Line Cook, Waiter, Barista. |
| `employment_type` | `Full-time`, `Part-time`, or `Casual`. |
| `hourly_rate` | Synthetic AUD hourly rate. |
| `standard_weekly_hours` | Typical contracted/expected weekly hours (informational; actual scheduling comes from shifts). |
| `active` | Whether this employee is currently eligible to be scheduled. |
| `synthetic_estimate` | Always `true`. |

## Generated tables (`data/raw/`, Phases 3-5)

Produced by `restaurant_ops.generation` (via `scripts/generate_data.py`)
from the seed tables above plus `config/simulation.yaml` and
`config/business_rules.yaml`. Reproducible from a seed: the same
`--seed` always produces byte-identical output (single
`numpy.random.Generator`, seeded once, threaded through every generator
function in a fixed call order: daily context -> shifts -> orders/order
items -> reviews -> inventory movements). All of it is synthetic.

### `daily_context.csv`

- **Purpose**: the calendar/weather table every other generator reads
  demand signals from.
- **Grain**: one row per business date.
- **Primary key**: `business_date`.
- **Foreign keys**: none.
- **Synthetic/public-source status**: `temperature_c`/`rain_mm` are a
  synthetic seasonal model (see `docs/limitations.md`); public holiday
  dates are computed from real Victorian public holiday rules (a
  calendar fact, not synthetic or confidential); `city_event_flag`
  marks fictional events.

| Column | Description |
|---|---|
| `business_date` | Calendar date. |
| `day_name` | Day of week, e.g. `Friday`. |
| `temperature_c` | Synthetic daily temperature. |
| `rain_mm` | Synthetic daily rainfall; `0.0` on dry days. |
| `weekend_flag` | Saturday or Sunday. |
| `public_holiday_flag` | A real Victorian public holiday. |
| `city_event_flag` | A fictional recurring city event. |
| `promotion_name` | The promotion scheduled for this weekday, if any (not every order redeems it — see `orders.promotion_name`). |

### `orders.csv`

- **Purpose**: one row per synthetic restaurant order.
- **Grain**: one row per order.
- **Primary key**: `order_id`.
- **Foreign keys**: none stored on this table (order items reference it).
- **Synthetic/public-source status**: entirely synthetic.

| Column | Description |
|---|---|
| `order_id` | Unique order identifier, e.g. `ORD012345`. |
| `order_timestamp` | Date and time the order was placed. |
| `business_date` | Calendar date, joins to `daily_context.business_date`. |
| `daypart` | `lunch` or `dinner`. |
| `channel` | `dine_in`, `pickup`, `uber_eats`, or `doordash`. |
| `status` | `Completed`, `Cancelled`, or `Partially Refunded`. |
| `table_number` | Set only for `dine_in`; null otherwise. |
| `customer_count` | Set only for `dine_in`; null otherwise. |
| `promotion_name` | Set only if this specific order redeemed the day's promotion. |
| `subtotal` | Sum of `order_items.line_total`. |
| `discount_amount` | Promotion discount applied to this order. |
| `refund_amount` | Non-zero only for `Cancelled` (full refund) or `Partially Refunded` (partial). |
| `platform_commission` | `(subtotal - discount_amount) x commission_rate`; zero for `dine_in`/`pickup` and for cancelled orders. |
| `net_sales` | `subtotal - discount_amount - refund_amount - platform_commission`. |
| `estimated_food_cost` | Sum of `order_items.estimated_line_food_cost`. |
| `estimated_gross_profit` | `net_sales - estimated_food_cost`. |
| `preparation_minutes` | Kitchen prep time, rises with `kitchen_load_ratio`. |
| `promised_minutes` | Channel-specific service promise (see `docs/business_rules.md`). |
| `late_flag` | Whether the order missed its promised time (delivery orders factor in a notional transit leg). |
| `missing_item_flag` | Whether one basket item was marked `Missing` on `order_items`. |
| `kitchen_staff_count` / `front_of_house_staff_count` | Phase 3 roster placeholder — see `docs/business_rules.md` staffing section. |
| `kitchen_load_ratio` | `orders_in_the_same_hour / estimated_kitchen_capacity`. |
| `temperature_c` / `rain_mm` | Copied from `daily_context` for this order's date, for convenience. |

### `order_items.csv`

- **Purpose**: the basket contents of every order.
- **Grain**: one row per (order, menu item line).
- **Primary key**: `order_item_id`.
- **Foreign keys**: `order_id` -> `orders.order_id`;
  `menu_item_id` -> `menu_items.menu_item_id`.
- **Synthetic/public-source status**: entirely synthetic.

| Column | Description |
|---|---|
| `order_item_id` | Unique line identifier, e.g. `OI0123456`. |
| `order_id` | The order this line belongs to. |
| `menu_item_id` | The menu item ordered. |
| `quantity` | Units ordered on this line. |
| `unit_price` | Menu selling price at time of order. |
| `estimated_unit_food_cost` | Per-serving estimated food cost (from `restaurant_ops.ingestion.loader.compute_menu_item_food_costs`). |
| `line_total` | `unit_price x quantity`. |
| `estimated_line_food_cost` | `estimated_unit_food_cost x quantity`. |
| `special_request` | Free-text request (e.g. "no coriander"), or null. |
| `item_status` | `Fulfilled` or `Missing`. Exactly one line is `Missing` when `orders.missing_item_flag` is true. |

### `reviews.csv`

- **Purpose**: a sampled subset of orders with a customer review.
- **Grain**: one row per review (not every order gets one).
- **Primary key**: `review_id`.
- **Foreign keys**: `order_id` -> `orders.order_id`.
- **Synthetic/public-source status**: entirely synthetic; review text is
  templated, not scraped.

| Column | Description |
|---|---|
| `review_id` | Unique review identifier, e.g. `REV001234`. |
| `order_id` | The order being reviewed. Never a `Cancelled` order. |
| `review_date` | A few days after `orders.business_date`, clamped to the simulation window. |
| `channel` | Copied from the order. |
| `rating` | 1-5, formula-driven (see `docs/business_rules.md`), never uniform random. |
| `review_text` | A template selected by rating band. |
| `complaint_category` | `"Missing Item"`, `"Late Order"`, a random category for other low ratings, or null. |
| `response_required_flag` | True if `rating <= 2` or a complaint category was assigned. |

### `employee_shifts.csv`

- **Purpose**: real scheduled shifts (including absences) — the source
  of the effective staffing that drives `orders.kitchen_load_ratio`.
- **Grain**: one row per scheduled shift.
- **Primary key**: `shift_id`.
- **Foreign keys**: `employee_id` -> `employees.employee_id`.
- **Synthetic/public-source status**: entirely synthetic. Note: this
  table intentionally has no `daypart` column (matching the spec's exact
  required columns) — `restaurant_ops.generation.staffing.generate_shifts`
  returns a separate `(business_date, daypart) -> (kitchen_count,
  front_of_house_count)` lookup alongside it for `orders.py` to consume.

| Column | Description |
|---|---|
| `shift_id` | Unique shift identifier, e.g. `SFT001234`. |
| `employee_id` | The scheduled employee. |
| `business_date` | The date of the shift. |
| `role` | Copied from the employee record at schedule time. |
| `shift_start` / `shift_end` | Includes a prep buffer before daypart service hours (see `docs/business_rules.md`). |
| `break_minutes` | Non-zero only for shifts longer than `staffing.break_minutes_threshold_hours`. |
| `scheduled_hours` | `shift_end - shift_start`, in hours. |
| `actual_hours` | `0` if `absence_flag` is true; otherwise scheduled hours minus break, plus small random variance. |
| `absence_flag` | Whether this employee didn't show up for the shift. |
| `hourly_rate` | Copied from the employee record. |
| `labour_cost` | `actual_hours x hourly_rate`. |

### `inventory_movements.csv`

- **Purpose**: a full stock ledger per ingredient — deliveries,
  consumption, waste, expiry, and stocktake adjustments.
- **Grain**: one row per movement event.
- **Primary key**: `movement_id`.
- **Foreign keys**: `ingredient_id` -> `ingredients.ingredient_id`.
- **Synthetic/public-source status**: entirely synthetic.

| Column | Description |
|---|---|
| `movement_id` | Unique movement identifier, e.g. `MOV0012345`. |
| `movement_timestamp` | When this movement was applied — see `docs/business_rules.md` for why intra-day ordering matters here. |
| `business_date` | Calendar date of the movement. |
| `ingredient_id` | The ingredient affected. |
| `movement_type` | `Supplier Delivery`, `Sales Consumption`, `Waste`, `Stock Adjustment`, or `Expired Stock`. |
| `quantity_change` | Positive for deliveries and upward stock adjustments; negative for consumption, waste, expiry, and downward adjustments. |
| `unit` | Matches `ingredients.unit`. |
| `unit_cost` | Normally `ingredients.estimated_unit_cost`; inflated by `inventory.emergency_cost_multiplier` on same-day emergency deliveries. |
| `movement_value` | `quantity_change x unit_cost`. |
| `reference_id` | A delivery/adjustment/expiry ID, the business date (for daily-aggregated consumption/waste), or `"INIT-STOCKTAKE"` for each ingredient's opening balance. |

Running per-ingredient balance (`quantity_change` summed in
`movement_timestamp` order) never goes negative — enforced by
`restaurant_ops.validation.rules.validate_inventory_movements` and
covered by `tests/unit/test_inventory.py`.

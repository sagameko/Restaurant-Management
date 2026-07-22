# Data dictionary

Documents every table as it is implemented. Only the seed layer exists so
far (Phase 1 / Phase 2 slice); generated tables (orders, shifts, reviews,
inventory movements, ...) will be added here as later phases land.

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

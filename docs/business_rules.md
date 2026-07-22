# Business rules

Documents the modelling assumptions behind the synthetic data, as they are
implemented. Only the food-cost calculation exists so far (Phase 1 /
Phase 2 slice). Sections for demand, staffing, inventory-reorder,
review-generation and menu-engineering rules will be added as those
phases land — see `PROGRESS.md`.

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

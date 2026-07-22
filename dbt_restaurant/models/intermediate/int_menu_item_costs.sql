-- Recomputes estimated food cost per menu item directly in SQL from
-- stg_recipes x stg_ingredients, mirroring
-- restaurant_ops.ingestion.loader.compute_menu_item_food_costs (Phase 2)
-- so the dbt layer doesn't have to trust a Python-computed column it
-- can't independently verify.
with recipes as (
    select * from {{ ref('stg_recipes') }}
),

ingredients as (
    select * from {{ ref('stg_ingredients') }}
),

menu_items as (
    select * from {{ ref('stg_menu_items') }}
),

recipe_costs as (
    select
        recipes.menu_item_id,
        sum(
            recipes.quantity_required
            * ingredients.estimated_unit_cost
            * (1 + recipes.estimated_wastage_pct)
        ) as estimated_item_food_cost
    from recipes
    inner join ingredients on recipes.ingredient_id = ingredients.ingredient_id
    group by recipes.menu_item_id
)

select
    menu_items.menu_item_id,
    menu_items.item_name,
    menu_items.category,
    menu_items.selling_price,
    recipe_costs.estimated_item_food_cost,
    menu_items.selling_price - recipe_costs.estimated_item_food_cost as estimated_gross_profit,
    case
        when menu_items.selling_price > 0
            then (menu_items.selling_price - recipe_costs.estimated_item_food_cost) / menu_items.selling_price
    end as estimated_gross_margin_pct
from menu_items
inner join recipe_costs on menu_items.menu_item_id = recipe_costs.menu_item_id

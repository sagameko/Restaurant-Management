-- Grain: one row per ingredient — a current-state snapshot (closing
-- stock, run rate, risk), not a daily trend like the other marts.
with movements as (
    select * from {{ ref('fact_inventory_movements') }}
),

closing as (
    select ingredient_id, sum(quantity_change) as closing_quantity, sum(movement_value) as closing_value
    from movements
    group by ingredient_id
),

waste as (
    select ingredient_id, sum(-quantity_change) as waste_quantity, sum(-movement_value) as waste_value
    from movements
    where movement_type = 'Waste'
    group by ingredient_id
),

expired as (
    select ingredient_id, sum(-quantity_change) as expired_quantity, sum(-movement_value) as expired_value
    from movements
    where movement_type = 'Expired Stock'
    group by ingredient_id
),

consumption as (
    select ingredient_id, avg(quantity_consumed) as avg_daily_consumption
    from {{ ref('int_ingredient_consumption') }}
    group by ingredient_id
),

emergency_deliveries as (
    select ingredient_id, count(*) as emergency_delivery_count
    from movements
    where movement_type = 'Supplier Delivery' and reference_id like '%EMERGENCY%'
    group by ingredient_id
),

affected_menu_items as (
    select recipes.ingredient_id, string_agg(distinct dim_menu_item.item_name, ', ') as affected_menu_items
    from {{ ref('stg_recipes') }} as recipes
    inner join {{ ref('dim_menu_item') }} on recipes.menu_item_id = dim_menu_item.menu_item_id
    group by recipes.ingredient_id
)

select
    dim_ingredient.ingredient_id,
    dim_ingredient.ingredient_name,
    dim_ingredient.ingredient_category,
    dim_ingredient.unit,
    dim_ingredient.reorder_level,
    dim_ingredient.safety_stock,
    dim_ingredient.supplier_name,
    dim_ingredient.supplier_lead_time_days,
    coalesce(closing.closing_quantity, 0) as closing_quantity,
    coalesce(closing.closing_value, 0) as closing_value,
    coalesce(closing.closing_quantity, 0) < dim_ingredient.reorder_level as is_reorder_alert,
    coalesce(consumption.avg_daily_consumption, 0) as avg_daily_consumption,
    case
        when consumption.avg_daily_consumption > 0
            then closing.closing_quantity / consumption.avg_daily_consumption
    end as estimated_days_of_stock_remaining,
    coalesce(waste.waste_quantity, 0) as total_waste_quantity,
    coalesce(waste.waste_value, 0) as total_waste_value,
    coalesce(expired.expired_quantity, 0) as total_expired_quantity,
    coalesce(expired.expired_value, 0) as total_expired_value,
    coalesce(emergency_deliveries.emergency_delivery_count, 0) as emergency_delivery_count,
    affected_menu_items.affected_menu_items
from {{ ref('dim_ingredient') }}
left join closing on dim_ingredient.ingredient_id = closing.ingredient_id
left join waste on dim_ingredient.ingredient_id = waste.ingredient_id
left join expired on dim_ingredient.ingredient_id = expired.ingredient_id
left join consumption on dim_ingredient.ingredient_id = consumption.ingredient_id
left join emergency_deliveries on dim_ingredient.ingredient_id = emergency_deliveries.ingredient_id
left join affected_menu_items on dim_ingredient.ingredient_id = affected_menu_items.ingredient_id

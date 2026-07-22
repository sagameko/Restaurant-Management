-- Grain: one row per menu item.
with menu_items as (
    select * from {{ ref('stg_menu_items') }}
),

costs as (
    select * from {{ ref('int_menu_item_costs') }}
)

select
    menu_items.menu_item_id,
    menu_items.item_name,
    menu_items.category,
    menu_items.selling_price,
    menu_items.estimated_prep_minutes,
    menu_items.is_vegetarian,
    menu_items.is_vegan,
    menu_items.is_gluten_free,
    menu_items.is_available_for_delivery,
    menu_items.base_popularity_weight,
    menu_items.cold_weather_affinity,
    menu_items.hot_weather_affinity,
    menu_items.lunch_affinity,
    menu_items.dinner_affinity,
    menu_items.delivery_affinity,
    menu_items.source_type,
    costs.estimated_item_food_cost,
    costs.estimated_gross_profit,
    costs.estimated_gross_margin_pct
from menu_items
left join costs on menu_items.menu_item_id = costs.menu_item_id

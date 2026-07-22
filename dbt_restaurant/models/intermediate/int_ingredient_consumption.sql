with movements as (
    select * from {{ ref('stg_inventory_movements') }}
),

ingredients as (
    select * from {{ ref('stg_ingredients') }}
)

select
    movements.business_date,
    movements.ingredient_id,
    ingredients.ingredient_name,
    ingredients.ingredient_category,
    sum(
        case when movements.movement_type = 'Sales Consumption' then -movements.quantity_change else 0 end
    ) as quantity_consumed,
    sum(
        case when movements.movement_type = 'Sales Consumption' then -movements.movement_value else 0 end
    ) as consumption_value,
    sum(case when movements.movement_type = 'Waste' then -movements.quantity_change else 0 end) as quantity_wasted,
    sum(case when movements.movement_type = 'Waste' then -movements.movement_value else 0 end) as waste_value,
    sum(
        case when movements.movement_type = 'Expired Stock' then -movements.quantity_change else 0 end
    ) as quantity_expired,
    sum(
        case when movements.movement_type = 'Supplier Delivery' then movements.quantity_change else 0 end
    ) as quantity_delivered
from movements
inner join ingredients on movements.ingredient_id = ingredients.ingredient_id
group by movements.business_date, movements.ingredient_id, ingredients.ingredient_name, ingredients.ingredient_category

with source as (
    select * from {{ source('raw', 'order_items') }}
)

select
    order_item_id,
    order_id,
    menu_item_id,
    cast(quantity as integer) as quantity,
    cast(unit_price as decimal(10, 2)) as unit_price,
    cast(estimated_unit_food_cost as decimal(10, 4)) as estimated_unit_food_cost,
    cast(line_total as decimal(10, 2)) as line_total,
    cast(estimated_line_food_cost as decimal(10, 4)) as estimated_line_food_cost,
    nullif(trim(special_request), '') as special_request,
    trim(item_status) as item_status
from source

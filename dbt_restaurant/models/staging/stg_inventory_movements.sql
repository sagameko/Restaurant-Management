with source as (
    select * from {{ source('raw', 'inventory_movements') }}
)

select
    movement_id,
    cast(movement_timestamp as timestamp) as movement_timestamp,
    cast(business_date as date) as business_date,
    ingredient_id,
    trim(movement_type) as movement_type,
    cast(quantity_change as double) as quantity_change,
    lower(trim(unit)) as unit,
    cast(unit_cost as decimal(10, 4)) as unit_cost,
    cast(movement_value as decimal(10, 4)) as movement_value,
    trim(reference_id) as reference_id
from source

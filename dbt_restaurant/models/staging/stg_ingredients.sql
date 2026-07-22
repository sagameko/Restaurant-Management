with source as (
    select * from {{ source('raw', 'ingredients') }}
)

select
    ingredient_id,
    trim(ingredient_name) as ingredient_name,
    trim(ingredient_category) as ingredient_category,
    lower(trim(unit)) as unit,
    cast(estimated_unit_cost as decimal(10, 4)) as estimated_unit_cost,
    cast(shelf_life_days as integer) as shelf_life_days,
    cast(reorder_level as double) as reorder_level,
    cast(safety_stock as double) as safety_stock,
    supplier_id,
    synthetic_estimate as is_synthetic_estimate
from source

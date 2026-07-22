with source as (
    select * from {{ source('raw', 'recipes') }}
)

select
    menu_item_id,
    ingredient_id,
    cast(quantity_required as double) as quantity_required,
    lower(trim(unit)) as unit,
    cast(estimated_wastage_pct as double) as estimated_wastage_pct
from source

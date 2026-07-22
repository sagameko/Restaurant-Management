with source as (
    select * from {{ source('raw', 'menu_items') }}
)

select
    menu_item_id,
    trim(item_name) as item_name,
    trim(category) as category,
    cast(selling_price as decimal(10, 2)) as selling_price,
    cast(estimated_prep_minutes as integer) as estimated_prep_minutes,
    vegetarian as is_vegetarian,
    vegan as is_vegan,
    gluten_free as is_gluten_free,
    available_for_delivery as is_available_for_delivery,
    cast(base_popularity_weight as double) as base_popularity_weight,
    cast(cold_weather_affinity as double) as cold_weather_affinity,
    cast(hot_weather_affinity as double) as hot_weather_affinity,
    cast(lunch_affinity as double) as lunch_affinity,
    cast(dinner_affinity as double) as dinner_affinity,
    cast(delivery_affinity as double) as delivery_affinity,
    lower(trim(source_type)) as source_type,
    nullif(trim(cast(source_url as varchar)), '') as source_url
from source

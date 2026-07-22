-- Hourly kitchen load: one row per (business_date, hour, daypart),
-- reconstructing the same "orders in the same hour" window that
-- restaurant_ops.generation.orders used to compute kitchen_load_ratio.
with orders as (
    select * from {{ ref('stg_orders') }}
)

select
    business_date,
    daypart,
    extract(hour from order_timestamp) as order_hour,
    count(*) as order_count,
    avg(kitchen_load_ratio) as avg_kitchen_load_ratio,
    avg(preparation_minutes) as avg_preparation_minutes,
    sum(case when is_late then 1 else 0 end) as late_order_count,
    sum(case when has_missing_item then 1 else 0 end) as missing_item_order_count
from orders
group by business_date, daypart, extract(hour from order_timestamp)

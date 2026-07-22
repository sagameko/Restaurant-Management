-- Grain: one row per (business_date, daypart). Feeds the Service
-- Performance page. Distribution-style charts (a histogram of
-- individual order prep times) read fact_orders directly rather than
-- this mart, which summarizes.
with orders as (
    select * from {{ ref('fact_orders') }}
    where status != 'Cancelled'
)

select
    business_date,
    daypart,
    count(*) as order_count,
    avg(preparation_minutes) as average_preparation_minutes,
    median(preparation_minutes) as median_preparation_minutes,
    percentile_cont(0.9) within group (order by preparation_minutes) as p90_preparation_minutes,
    avg(case when is_late then 1.0 else 0.0 end) as late_order_pct,
    avg(case when has_missing_item then 1.0 else 0.0 end) as missing_item_pct,
    avg(case when status = 'Partially Refunded' then 1.0 else 0.0 end) as refund_pct,
    avg(kitchen_load_ratio) as average_kitchen_load_ratio,
    max(kitchen_load_ratio) as peak_kitchen_load_ratio,
    avg(kitchen_staff_count) as average_kitchen_staff_count,
    avg(front_of_house_staff_count) as average_front_of_house_staff_count
from orders
group by business_date, daypart

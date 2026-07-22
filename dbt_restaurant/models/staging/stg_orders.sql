with source as (
    select * from {{ source('raw', 'orders') }}
)

select
    order_id,
    cast(order_timestamp as timestamp) as order_timestamp,
    cast(business_date as date) as business_date,
    lower(trim(daypart)) as daypart,
    lower(trim(channel)) as channel,
    trim(status) as status,
    cast(table_number as integer) as table_number,
    cast(customer_count as integer) as customer_count,
    nullif(trim(promotion_name), '') as promotion_name,
    cast(subtotal as decimal(10, 2)) as subtotal,
    cast(discount_amount as decimal(10, 2)) as discount_amount,
    cast(refund_amount as decimal(10, 2)) as refund_amount,
    cast(platform_commission as decimal(10, 2)) as platform_commission,
    cast(net_sales as decimal(10, 2)) as net_sales,
    cast(estimated_food_cost as decimal(10, 4)) as estimated_food_cost,
    cast(estimated_gross_profit as decimal(10, 4)) as estimated_gross_profit,
    cast(preparation_minutes as double) as preparation_minutes,
    cast(promised_minutes as double) as promised_minutes,
    late_flag as is_late,
    missing_item_flag as has_missing_item,
    cast(kitchen_staff_count as integer) as kitchen_staff_count,
    cast(front_of_house_staff_count as integer) as front_of_house_staff_count,
    cast(kitchen_load_ratio as double) as kitchen_load_ratio,
    cast(temperature_c as double) as temperature_c,
    cast(rain_mm as double) as rain_mm
from source

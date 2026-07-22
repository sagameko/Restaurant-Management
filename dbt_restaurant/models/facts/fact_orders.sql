-- Grain: one row per restaurant order.
with orders as (
    select * from {{ ref('stg_orders') }}
),

financials as (
    select order_id, contribution_margin_pct, item_count, item_quantity_total
    from {{ ref('int_order_financials') }}
)

select
    orders.order_id,
    orders.order_timestamp,
    orders.business_date,
    orders.daypart,
    orders.channel,
    orders.status,
    orders.table_number,
    orders.customer_count,
    orders.promotion_name,
    orders.subtotal,
    orders.discount_amount,
    orders.refund_amount,
    orders.platform_commission,
    orders.net_sales,
    orders.estimated_food_cost,
    orders.estimated_gross_profit,
    financials.contribution_margin_pct,
    financials.item_count,
    financials.item_quantity_total,
    orders.preparation_minutes,
    orders.promised_minutes,
    orders.is_late,
    orders.has_missing_item,
    orders.kitchen_staff_count,
    orders.front_of_house_staff_count,
    orders.kitchen_load_ratio,
    orders.temperature_c,
    orders.rain_mm
from orders
left join financials on orders.order_id = financials.order_id

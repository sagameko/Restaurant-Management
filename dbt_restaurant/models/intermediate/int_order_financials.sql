with orders as (
    select * from {{ ref('stg_orders') }}
),

order_items as (
    select
        order_id,
        count(*) as item_count,
        sum(quantity) as item_quantity_total
    from {{ ref('stg_order_items') }}
    group by order_id
)

select
    orders.order_id,
    orders.business_date,
    orders.daypart,
    orders.channel,
    orders.status,
    orders.subtotal,
    orders.discount_amount,
    orders.refund_amount,
    orders.platform_commission,
    orders.net_sales,
    orders.estimated_food_cost,
    orders.estimated_gross_profit,
    case
        when orders.net_sales > 0 then orders.estimated_gross_profit / orders.net_sales
    end as contribution_margin_pct,
    coalesce(order_items.item_count, 0) as item_count,
    coalesce(order_items.item_quantity_total, 0) as item_quantity_total
from orders
left join order_items on orders.order_id = order_items.order_id

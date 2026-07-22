-- Grain: one row per channel. Feeds the Channel Profitability page.
-- Deliberately keeps gross sales (subtotal) and profitability
-- (estimated_gross_profit) as separate columns — the page's whole point
-- is showing they aren't the same metric (per spec).
--
-- Orders and reviews are aggregated to channel grain *separately*
-- before joining — joining the two un-aggregated, order-grain and
-- review-grain tables directly on channel would fan out into a
-- cross-product per channel (every order paired with every review on
-- that channel), wildly inflating every sum. See docs/development_log.md.
with orders_by_channel as (
    select
        channel,
        count(*) as order_count,
        sum(subtotal) as gross_sales,
        sum(platform_commission) as commission,
        sum(refund_amount) as refunds,
        sum(net_sales) as net_sales,
        sum(estimated_gross_profit) as estimated_gross_profit,
        avg(net_sales) as average_order_value,
        avg(preparation_minutes) as average_preparation_minutes,
        avg(case when is_late then 1.0 else 0.0 end) as late_order_pct
    from {{ ref('fact_orders') }}
    where status != 'Cancelled'
    group by channel
),

reviews_by_channel as (
    select channel, avg(rating) as average_rating
    from {{ ref('fact_reviews') }}
    where rating is not null
    group by channel
)

select
    dim_channel.channel,
    dim_channel.channel_label,
    dim_channel.is_delivery_channel,
    dim_channel.commission_rate,
    coalesce(orders_by_channel.order_count, 0) as order_count,
    coalesce(orders_by_channel.gross_sales, 0) as gross_sales,
    coalesce(orders_by_channel.commission, 0) as commission,
    coalesce(orders_by_channel.refunds, 0) as refunds,
    coalesce(orders_by_channel.net_sales, 0) as net_sales,
    coalesce(orders_by_channel.estimated_gross_profit, 0) as estimated_gross_profit,
    orders_by_channel.average_order_value,
    orders_by_channel.average_preparation_minutes,
    orders_by_channel.late_order_pct,
    reviews_by_channel.average_rating
from {{ ref('dim_channel') }}
left join orders_by_channel on dim_channel.channel = orders_by_channel.channel
left join reviews_by_channel on dim_channel.channel = reviews_by_channel.channel

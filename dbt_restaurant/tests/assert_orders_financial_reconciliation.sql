-- Fails if any order's net_sales doesn't reconcile (within a small
-- rounding tolerance) to subtotal - discount - refund - commission.
select
    order_id,
    subtotal,
    discount_amount,
    refund_amount,
    platform_commission,
    net_sales,
    subtotal - discount_amount - refund_amount - platform_commission as expected_net_sales
from {{ ref('fact_orders') }}
where abs(net_sales - (subtotal - discount_amount - refund_amount - platform_commission)) > 0.02

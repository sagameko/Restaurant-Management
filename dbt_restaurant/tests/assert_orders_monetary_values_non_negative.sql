-- orders.subtotal >= 0 and orders.net_sales >= 0 (spec's own example test).
select order_id, subtotal, net_sales
from {{ ref('fact_orders') }}
where subtotal < 0 or net_sales < 0

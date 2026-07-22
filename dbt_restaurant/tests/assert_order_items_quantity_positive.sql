-- order_items.quantity > 0 (spec's own example test).
select order_item_id, quantity
from {{ ref('fact_order_items') }}
where quantity <= 0

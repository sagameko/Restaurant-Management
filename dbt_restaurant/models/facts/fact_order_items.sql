-- Grain: one row per order line item. business_date/channel are carried
-- from the parent order purely for convenient filtering — they don't
-- change this table's grain.
with order_items as (
    select * from {{ ref('stg_order_items') }}
),

orders as (
    select order_id, business_date, daypart, channel from {{ ref('stg_orders') }}
)

select
    order_items.order_item_id,
    order_items.order_id,
    order_items.menu_item_id,
    orders.business_date,
    orders.daypart,
    orders.channel,
    order_items.quantity,
    order_items.unit_price,
    order_items.estimated_unit_food_cost,
    order_items.line_total,
    order_items.estimated_line_food_cost,
    order_items.special_request,
    order_items.item_status
from order_items
inner join orders on order_items.order_id = orders.order_id

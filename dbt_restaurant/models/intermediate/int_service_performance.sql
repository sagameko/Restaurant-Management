-- Review-to-order relationships: one row per order, left-joined to its
-- review (if any) so service-outcome analysis doesn't have to repeat
-- this join in every downstream mart.
with orders as (
    select * from {{ ref('stg_orders') }}
),

reviews as (
    select * from {{ ref('stg_reviews') }}
)

select
    orders.order_id,
    orders.business_date,
    orders.daypart,
    orders.channel,
    orders.status,
    orders.is_late,
    orders.has_missing_item,
    orders.kitchen_load_ratio,
    orders.preparation_minutes,
    orders.promised_minutes,
    reviews.review_id,
    reviews.rating,
    reviews.complaint_category,
    reviews.is_response_required
from orders
left join reviews on orders.order_id = reviews.order_id

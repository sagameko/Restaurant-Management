-- Grain: one row per customer review.
with reviews as (
    select * from {{ ref('stg_reviews') }}
),

orders as (
    select order_id, business_date, daypart from {{ ref('stg_orders') }}
)

select
    reviews.review_id,
    reviews.order_id,
    orders.business_date,
    orders.daypart,
    reviews.review_date,
    reviews.channel,
    reviews.rating,
    reviews.review_text,
    reviews.complaint_category,
    reviews.is_response_required
from reviews
left join orders on reviews.order_id = orders.order_id

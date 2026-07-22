-- Grain: one row per review. Feeds the Customer Experience page.
-- Rating trend/distribution/by-channel/by-daypart charts all group by
-- this table's own columns; nothing needs pre-aggregating further.
with reviews as (
    select * from {{ ref('fact_reviews') }}
),

orders as (
    select order_id, preparation_minutes from {{ ref('fact_orders') }}
),

dates as (
    select business_date, day_name from {{ ref('dim_date') }}
)

select
    reviews.review_id,
    reviews.order_id,
    reviews.business_date,
    dates.day_name,
    reviews.daypart,
    reviews.channel,
    reviews.review_date,
    reviews.rating,
    reviews.review_text,
    reviews.complaint_category,
    reviews.is_response_required,
    orders.preparation_minutes,
    case
        when orders.preparation_minutes < 15 then 'Under 15 min'
        when orders.preparation_minutes < 25 then '15-25 min'
        when orders.preparation_minutes < 35 then '25-35 min'
        else 'Over 35 min'
    end as preparation_time_band
from reviews
left join orders on reviews.order_id = orders.order_id
left join dates on reviews.business_date = dates.business_date

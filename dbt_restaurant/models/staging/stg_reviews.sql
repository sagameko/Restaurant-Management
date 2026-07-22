with source as (
    select * from {{ source('raw', 'reviews') }}
)

select
    review_id,
    order_id,
    cast(review_date as date) as review_date,
    lower(trim(channel)) as channel,
    cast(rating as integer) as rating,
    trim(review_text) as review_text,
    nullif(trim(complaint_category), '') as complaint_category,
    response_required_flag as is_response_required
from source

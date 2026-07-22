with source as (
    select * from {{ source('raw', 'daily_context') }}
)

select
    cast(business_date as date) as business_date,
    trim(day_name) as day_name,
    cast(temperature_c as double) as temperature_c,
    cast(rain_mm as double) as rain_mm,
    weekend_flag as is_weekend,
    public_holiday_flag as is_public_holiday,
    city_event_flag as is_city_event,
    nullif(trim(promotion_name), '') as promotion_name
from source

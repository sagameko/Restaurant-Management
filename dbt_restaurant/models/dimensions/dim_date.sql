-- Grain: one row per business date in the simulation window.
with daily_context as (
    select * from {{ ref('stg_daily_context') }}
)

select
    business_date,
    day_name,
    extract(year from business_date) as year,
    extract(month from business_date) as month,
    extract(quarter from business_date) as quarter,
    extract(week from business_date) as week_of_year,
    extract(dayofyear from business_date) as day_of_year,
    is_weekend,
    is_public_holiday,
    is_city_event,
    promotion_name,
    temperature_c,
    rain_mm
from daily_context

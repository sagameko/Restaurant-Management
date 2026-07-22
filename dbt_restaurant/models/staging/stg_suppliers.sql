with source as (
    select * from {{ source('raw', 'suppliers') }}
)

select
    supplier_id,
    trim(supplier_name) as supplier_name,
    trim(supplier_category) as supplier_category,
    cast(average_lead_time_days as integer) as average_lead_time_days,
    cast(reliability_score as double) as reliability_score,
    synthetic_estimate as is_synthetic_estimate
from source

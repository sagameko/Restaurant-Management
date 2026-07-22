with source as (
    select * from {{ source('raw', 'employee_shifts') }}
)

select
    shift_id,
    employee_id,
    cast(business_date as date) as business_date,
    trim(role) as role,
    cast(shift_start as timestamp) as shift_start,
    cast(shift_end as timestamp) as shift_end,
    cast(break_minutes as integer) as break_minutes,
    cast(scheduled_hours as double) as scheduled_hours,
    cast(actual_hours as double) as actual_hours,
    absence_flag as is_absent,
    cast(hourly_rate as decimal(10, 2)) as hourly_rate,
    cast(labour_cost as decimal(10, 2)) as labour_cost
from source

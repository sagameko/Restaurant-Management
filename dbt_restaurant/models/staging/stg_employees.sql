with source as (
    select * from {{ source('raw', 'employees') }}
)

select
    employee_id,
    trim(employee_name) as employee_name,
    trim(department) as department,
    trim(role) as role,
    trim(employment_type) as employment_type,
    cast(hourly_rate as decimal(10, 2)) as hourly_rate,
    cast(standard_weekly_hours as double) as standard_weekly_hours,
    active as is_active,
    synthetic_estimate as is_synthetic_estimate
from source

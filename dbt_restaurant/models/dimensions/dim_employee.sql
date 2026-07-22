-- Grain: one row per employee.
select
    employee_id,
    employee_name,
    department,
    role,
    employment_type,
    hourly_rate,
    standard_weekly_hours,
    is_active
from {{ ref('stg_employees') }}

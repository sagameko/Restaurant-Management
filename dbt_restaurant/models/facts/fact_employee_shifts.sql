-- Grain: one row per scheduled employee shift.
with shifts as (
    select
        *,
        case
            when extract(hour from shift_start) < 13 then 'lunch'
            else 'dinner'
        end as daypart
    from {{ ref('stg_employee_shifts') }}
),

employees as (
    select employee_id, department from {{ ref('stg_employees') }}
)

select
    shifts.shift_id,
    shifts.employee_id,
    employees.department,
    shifts.business_date,
    shifts.daypart,
    shifts.role,
    shifts.shift_start,
    shifts.shift_end,
    shifts.break_minutes,
    shifts.scheduled_hours,
    shifts.actual_hours,
    shifts.is_absent,
    shifts.hourly_rate,
    shifts.labour_cost
from shifts
left join employees on shifts.employee_id = employees.employee_id

-- Labour cost by date and daypart. Shifts don't carry a daypart column
-- (matching the spec's exact required Employee shifts schema), so it's
-- inferred from shift_start: lunch shifts start ~10:45-11:00, dinner
-- shifts start ~14:45-15:00 (see config/business_rules.yaml: dayparts
-- and staffing.shift_buffer_before_hours) — 13:00 is a safe midpoint
-- threshold between the two.
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
    select * from {{ ref('stg_employees') }}
)

select
    shifts.business_date,
    shifts.daypart,
    employees.department,
    count(*) as shift_count,
    sum(case when shifts.is_absent then 1 else 0 end) as absence_count,
    sum(shifts.scheduled_hours) as total_scheduled_hours,
    sum(shifts.actual_hours) as total_actual_hours,
    sum(shifts.labour_cost) as total_labour_cost
from shifts
inner join employees on shifts.employee_id = employees.employee_id
group by shifts.business_date, shifts.daypart, employees.department

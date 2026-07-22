-- shift_end > shift_start (spec's own example test).
select shift_id, shift_start, shift_end
from {{ ref('fact_employee_shifts') }}
where shift_end <= shift_start

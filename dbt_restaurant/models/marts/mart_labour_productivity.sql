-- Grain: one row per (business_date, daypart). Feeds the Labour
-- Productivity page. Staffing-level flag thresholds: avg kitchen_load_ratio
-- above 1.2 is flagged Understaffed, below 0.5 is flagged Overstaffed,
-- otherwise Balanced — the same load ratio that drives preparation time
-- and service outcomes in restaurant_ops.generation.orders.
with labour as (
    select * from {{ ref('int_shift_labour_costs') }}
),

kitchen as (
    select business_date, daypart, shift_count, absence_count, total_scheduled_hours, total_actual_hours, total_labour_cost
    from labour
    where department = 'Kitchen'
),

front_of_house as (
    select business_date, daypart, shift_count, absence_count, total_scheduled_hours, total_actual_hours, total_labour_cost
    from labour
    where department = 'Front of House'
),

combined as (
    select
        coalesce(kitchen.business_date, front_of_house.business_date) as business_date,
        coalesce(kitchen.daypart, front_of_house.daypart) as daypart,
        coalesce(kitchen.total_scheduled_hours, 0) as kitchen_scheduled_hours,
        coalesce(front_of_house.total_scheduled_hours, 0) as front_of_house_scheduled_hours,
        coalesce(kitchen.total_actual_hours, 0) as kitchen_actual_hours,
        coalesce(front_of_house.total_actual_hours, 0) as front_of_house_actual_hours,
        coalesce(kitchen.total_labour_cost, 0) as kitchen_labour_cost,
        coalesce(front_of_house.total_labour_cost, 0) as front_of_house_labour_cost,
        coalesce(kitchen.absence_count, 0) + coalesce(front_of_house.absence_count, 0) as absence_count,
        coalesce(kitchen.shift_count, 0) + coalesce(front_of_house.shift_count, 0) as scheduled_shift_count
    from kitchen
    full outer join front_of_house
        on kitchen.business_date = front_of_house.business_date and kitchen.daypart = front_of_house.daypart
),

orders as (
    select business_date, daypart, count(*) as order_count, sum(net_sales) as net_sales
    from {{ ref('fact_orders') }}
    where status != 'Cancelled'
    group by business_date, daypart
),

load as (
    select business_date, daypart, avg(avg_kitchen_load_ratio) as avg_kitchen_load_ratio
    from {{ ref('int_hourly_demand') }}
    group by business_date, daypart
)

select
    combined.business_date,
    combined.daypart,
    combined.kitchen_scheduled_hours + combined.front_of_house_scheduled_hours as total_scheduled_hours,
    combined.kitchen_actual_hours + combined.front_of_house_actual_hours as total_actual_hours,
    combined.kitchen_labour_cost + combined.front_of_house_labour_cost as total_labour_cost,
    combined.kitchen_actual_hours,
    combined.front_of_house_actual_hours,
    combined.kitchen_labour_cost,
    combined.front_of_house_labour_cost,
    combined.absence_count,
    combined.scheduled_shift_count,
    coalesce(orders.order_count, 0) as order_count,
    coalesce(orders.net_sales, 0) as net_sales,
    case
        when (combined.kitchen_actual_hours + combined.front_of_house_actual_hours) > 0
            then orders.order_count / (combined.kitchen_actual_hours + combined.front_of_house_actual_hours)
    end as orders_per_labour_hour,
    case
        when (combined.kitchen_actual_hours + combined.front_of_house_actual_hours) > 0
            then orders.net_sales / (combined.kitchen_actual_hours + combined.front_of_house_actual_hours)
    end as revenue_per_labour_hour,
    case
        when combined.kitchen_actual_hours > 0 then orders.order_count / combined.kitchen_actual_hours
    end as orders_per_kitchen_labour_hour,
    case
        when combined.front_of_house_actual_hours > 0
            then orders.order_count / combined.front_of_house_actual_hours
    end as orders_per_front_of_house_labour_hour,
    case
        when orders.net_sales > 0
            then (combined.kitchen_labour_cost + combined.front_of_house_labour_cost) / orders.net_sales
    end as labour_cost_pct,
    load.avg_kitchen_load_ratio,
    case
        when load.avg_kitchen_load_ratio > 1.2 then 'Understaffed'
        when load.avg_kitchen_load_ratio < 0.5 then 'Overstaffed'
        else 'Balanced'
    end as staffing_level_flag
from combined
left join orders on combined.business_date = orders.business_date and combined.daypart = orders.daypart
left join load on combined.business_date = load.business_date and combined.daypart = load.daypart

-- Grain: one row per business date. Feeds the Executive Overview page.
-- Daypart-level and hourly cuts (e.g. "orders by daypart", "prep time
-- over time") are read directly from fact_orders/int_hourly_demand by
-- the app rather than pre-aggregated here.
with date_spine as (
    select * from {{ ref('dim_date') }}
),

orders as (
    select
        business_date,
        count(*) as order_count,
        sum(net_sales) as net_sales,
        sum(estimated_food_cost) as estimated_food_cost,
        sum(estimated_gross_profit) as estimated_gross_profit,
        avg(net_sales) as average_order_value,
        avg(preparation_minutes) as average_preparation_minutes,
        avg(case when is_late then 1.0 else 0.0 end) as late_order_pct
    from {{ ref('fact_orders') }}
    where status != 'Cancelled'
    group by business_date
),

labour as (
    select business_date, sum(total_labour_cost) as labour_cost
    from {{ ref('int_shift_labour_costs') }}
    group by business_date
),

reviews as (
    select business_date, avg(rating) as average_rating
    from {{ ref('fact_reviews') }}
    where rating is not null
    group by business_date
),

waste as (
    select business_date, sum(-movement_value) as waste_cost
    from {{ ref('fact_inventory_movements') }}
    where movement_type = 'Waste'
    group by business_date
)

select
    date_spine.business_date,
    date_spine.day_name,
    date_spine.is_weekend,
    date_spine.is_public_holiday,
    date_spine.is_city_event,
    date_spine.promotion_name,
    date_spine.temperature_c,
    date_spine.rain_mm,
    coalesce(orders.order_count, 0) as order_count,
    coalesce(orders.net_sales, 0) as net_sales,
    coalesce(orders.estimated_food_cost, 0) as estimated_food_cost,
    coalesce(orders.estimated_gross_profit, 0) as estimated_gross_profit,
    case
        when orders.net_sales > 0 then orders.estimated_gross_profit / orders.net_sales
    end as estimated_gross_margin_pct,
    orders.average_order_value,
    orders.average_preparation_minutes,
    orders.late_order_pct,
    coalesce(labour.labour_cost, 0) as labour_cost,
    case
        when orders.net_sales > 0 then labour.labour_cost / orders.net_sales
    end as labour_cost_pct,
    reviews.average_rating,
    coalesce(waste.waste_cost, 0) as waste_cost
from date_spine
left join orders on date_spine.business_date = orders.business_date
left join labour on date_spine.business_date = labour.business_date
left join reviews on date_spine.business_date = reviews.business_date
left join waste on date_spine.business_date = waste.business_date

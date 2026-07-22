-- Grain: one row per menu item. Feeds the Menu Engineering page.
--
-- Classification thresholds (documented per spec requirement): an item
-- is "High" popularity if its units_sold is at or above the median
-- units_sold across all menu items, and "High" profitability if its
-- contribution_margin_pct is at or above the median contribution
-- margin percentage across all menu items. The classic four-quadrant
-- label follows directly from those two:
--   Star      = High popularity + High profitability
--   Plowhorse = High popularity + Low profitability
--   Puzzle    = Low popularity + High profitability
--   Dog       = Low popularity + Low profitability
-- Only "Fulfilled" items on non-cancelled orders count as sold.
with eligible_items as (
    select fact_order_items.*
    from {{ ref('fact_order_items') }} as fact_order_items
    inner join {{ ref('fact_orders') }} as fact_orders
        on fact_order_items.order_id = fact_orders.order_id
    where fact_orders.status != 'Cancelled'
        and fact_order_items.item_status = 'Fulfilled'
),

item_stats as (
    select
        menu_item_id,
        sum(quantity) as units_sold,
        sum(line_total) as revenue,
        sum(estimated_line_food_cost) as estimated_food_cost,
        count(distinct order_id) as orders_containing_item,
        avg(quantity) as average_quantity_per_order
    from eligible_items
    group by menu_item_id
),

item_margins as (
    select
        *,
        revenue - estimated_food_cost as estimated_contribution_margin,
        case when revenue > 0 then (revenue - estimated_food_cost) / revenue end as contribution_margin_pct
    from item_stats
),

total_orders as (
    select count(*) as total_order_count
    from {{ ref('fact_orders') }}
    where status != 'Cancelled'
),

category_totals as (
    select dim_menu_item.category, sum(item_margins.revenue) as category_revenue
    from item_margins
    inner join {{ ref('dim_menu_item') }} on item_margins.menu_item_id = dim_menu_item.menu_item_id
    group by dim_menu_item.category
),

thresholds as (
    select
        median(units_sold) as median_units_sold,
        median(contribution_margin_pct) as median_margin_pct
    from item_margins
)

select
    dim_menu_item.menu_item_id,
    dim_menu_item.item_name,
    dim_menu_item.category,
    dim_menu_item.selling_price,
    coalesce(item_margins.units_sold, 0) as units_sold,
    coalesce(item_margins.revenue, 0) as revenue,
    coalesce(item_margins.estimated_food_cost, 0) as estimated_food_cost,
    coalesce(item_margins.estimated_contribution_margin, 0) as estimated_contribution_margin,
    item_margins.contribution_margin_pct,
    case
        when total_orders.total_order_count > 0
            then item_margins.orders_containing_item::double / total_orders.total_order_count
    end as order_penetration,
    item_margins.average_quantity_per_order,
    rank() over (partition by dim_menu_item.category order by item_margins.revenue desc) as sales_rank_within_category,
    case
        when category_totals.category_revenue > 0 then item_margins.revenue / category_totals.category_revenue
    end as revenue_pct_within_category,
    case
        when coalesce(item_margins.units_sold, 0) >= thresholds.median_units_sold then 'High'
        else 'Low'
    end as popularity_classification,
    case
        when coalesce(item_margins.contribution_margin_pct, 0) >= thresholds.median_margin_pct then 'High'
        else 'Low'
    end as profitability_classification,
    case
        when coalesce(item_margins.units_sold, 0) >= thresholds.median_units_sold
            and coalesce(item_margins.contribution_margin_pct, 0) >= thresholds.median_margin_pct
            then 'Star'
        when coalesce(item_margins.units_sold, 0) >= thresholds.median_units_sold then 'Plowhorse'
        when coalesce(item_margins.contribution_margin_pct, 0) >= thresholds.median_margin_pct then 'Puzzle'
        else 'Dog'
    end as menu_engineering_classification
from {{ ref('dim_menu_item') }}
left join item_margins on dim_menu_item.menu_item_id = item_margins.menu_item_id
left join category_totals on dim_menu_item.category = category_totals.category
cross join total_orders
cross join thresholds

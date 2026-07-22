-- Grain: one row per inventory ledger movement.
select
    movement_id,
    movement_timestamp,
    business_date,
    ingredient_id,
    movement_type,
    quantity_change,
    unit,
    unit_cost,
    movement_value,
    reference_id
from {{ ref('stg_inventory_movements') }}

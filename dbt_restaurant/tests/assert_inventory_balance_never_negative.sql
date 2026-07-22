-- Custom inventory-balance reconciliation test: the running per-ingredient
-- stock balance (movements summed in true chronological order) must
-- never go negative — see docs/business_rules.md for why movement
-- timestamps within a business date matter here.
with running_balance as (
    select
        movement_id,
        ingredient_id,
        movement_timestamp,
        sum(quantity_change) over (
            partition by ingredient_id
            order by movement_timestamp
            rows between unbounded preceding and current row
        ) as balance
    from {{ ref('fact_inventory_movements') }}
)

select movement_id, ingredient_id, movement_timestamp, balance
from running_balance
where balance < -0.01

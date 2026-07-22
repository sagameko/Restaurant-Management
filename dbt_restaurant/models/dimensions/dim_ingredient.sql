-- Grain: one row per ingredient.
with ingredients as (
    select * from {{ ref('stg_ingredients') }}
),

suppliers as (
    select * from {{ ref('stg_suppliers') }}
)

select
    ingredients.ingredient_id,
    ingredients.ingredient_name,
    ingredients.ingredient_category,
    ingredients.unit,
    ingredients.estimated_unit_cost,
    ingredients.shelf_life_days,
    ingredients.reorder_level,
    ingredients.safety_stock,
    ingredients.supplier_id,
    suppliers.supplier_name,
    suppliers.average_lead_time_days as supplier_lead_time_days,
    suppliers.reliability_score as supplier_reliability_score
from ingredients
left join suppliers on ingredients.supplier_id = suppliers.supplier_id

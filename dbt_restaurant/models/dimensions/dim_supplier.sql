-- Grain: one row per supplier.
select
    supplier_id,
    supplier_name,
    supplier_category,
    average_lead_time_days,
    reliability_score
from {{ ref('stg_suppliers') }}

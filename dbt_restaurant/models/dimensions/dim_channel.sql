-- Grain: one row per order channel. Sourced from a dbt seed
-- (seeds/channel_reference.csv) rather than raw data, since channel
-- metadata (label, commission rate) is fixed reference information, not
-- something the generator produces. Kept in sync with
-- config/simulation.yaml's channel commission rates by hand — see
-- docs/business_rules.md.
select
    channel,
    channel_label,
    is_delivery_channel,
    commission_rate
from {{ ref('channel_reference') }}

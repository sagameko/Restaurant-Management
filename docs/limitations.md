# Limitations

Honest caveats about what this dataset is and isn't, updated as each
phase lands (currently: Phase 1-5).

- **Synthetic data cannot validate actual business performance.** Every
  number in this project — costs, margins, demand patterns, ratings — is
  generated from configurable rules, not observed from a real restaurant.
  It demonstrates a data platform and a plausible operational story, not
  Bon Bon Boy's or any real restaurant's actual performance.
- **Ingredient costs are estimates.** `ingredients.estimated_unit_cost`
  and everything derived from it (food cost, gross margin) are
  hand-authored plausible figures, not real supplier pricing.
- **Demand relationships are intentionally simulated.** Day-of-week,
  weather, promotion and holiday effects on order volume are modelled
  multiplicatively from constants in `config/business_rules.yaml`, tuned
  to produce directionally realistic patterns (see
  `docs/business_rules.md`) — not fitted to any real sales data.
- **Weather is synthetic in version one.** `daily_context.temperature_c`
  and `rain_mm` come from a seasonal cosine model for Melbourne plus
  random noise, not the Bureau of Meteorology or any historical record.
  Public holiday dates are the exception: those are computed from the
  actual Victorian public holiday rules, since they're calendar facts,
  not weather.
- **Staffing is scheduled against a fixed target roster, not real
  labour-demand forecasting.** `employees.csv` is generated, and shifts
  are real (including random absences that move `kitchen_load_ratio`),
  but the *target* headcount per shift
  (`config/business_rules.yaml: kitchen_capacity.staff_roster`) is a
  small number of hand-tuned constants, not the output of a rostering
  algorithm reacting to forecast demand.
- **Employees never call in sick for a reason, take leave, or have shift
  preferences.** Absence is a flat 4% independent probability per
  scheduled shift (`staffing.absence_probability`) — there's no
  correlation with day of week, weather, or a specific employee being
  less reliable than another.
- **Inventory never actually stocks out.** The reorder + same-day
  emergency-purchasing logic (`docs/business_rules.md`) guarantees the
  simulated ledger never goes negative — in reality, restaurants
  sometimes do run out of an ingredient and have to pull a dish from the
  menu until the next delivery. This dataset doesn't model that failure
  mode; it models a kitchen that always
  manages to source what it needs, at a cost premium when it's urgent.
- **Waste and expiry rates are illustrative,** not modelled from any
  particular ingredient's real spoilage behaviour beyond using
  `shelf_life_days` as a relative signal (shorter shelf life -> expires
  more often).
- **Customer reviews are generated templates.** `reviews.review_text` is
  selected from a small set of hand-written sentences keyed by rating
  band, not scraped or adapted from real reviews. `reviews.rating` is
  formula-driven from operational outcomes plus noise (see
  `docs/business_rules.md`), not sampled from any real rating
  distribution.
- **Platform commission rates are modelling assumptions.**
  `config/simulation.yaml: channels.*.commission_rate` are plausible
  illustrative figures for Uber Eats/DoorDash-style commissions, not
  contracted or publicly confirmed rates for any specific platform or
  restaurant.
- **Menu item names/categories/prices are illustrative, not scraped.**
  See `docs/data_dictionary.md` and the README disclaimer — a
  representative Vietnamese menu, not a reproduction of any live site's
  current offering.
- **`dim_channel`'s commission rates are a hand-kept duplicate.** They're
  sourced from a dbt seed (`seeds/channel_reference.csv`) rather than
  derived from `config/simulation.yaml`, since dbt seeds can't read
  Python config at build time. If `simulation.yaml`'s commission rates
  ever change, this seed needs updating manually — see
  `docs/architecture.md`.
- **`mart_inventory_risk` is a single current-state snapshot,** not a
  daily trend — closing stock, waste totals, and reorder alerts all
  reflect the *end* of whatever date range was generated, not any
  particular day within it. Combined with inventory never actually
  stocking out (above), a "reorder alert" here just means closing stock
  ended up below the reorder level, not that a stockout was ever close.
- **Menu-engineering classification thresholds are median-based and
  self-relative,** not benchmarked against real restaurant menu
  engineering practice. An item is "High" popularity/profitability only
  relative to this menu's own median — see `docs/business_rules.md` for
  the exact definition.

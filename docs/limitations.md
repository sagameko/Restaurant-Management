# Limitations

Honest caveats about what this dataset is and isn't, updated as each
phase lands (currently: Phase 1-3).

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
- **Kitchen/front-of-house staffing is a Phase 3 placeholder.**
  `orders.kitchen_staff_count`, `front_of_house_staff_count` and
  therefore `kitchen_load_ratio` and `preparation_minutes` come from a
  fixed roster table by daypart/weekday-type
  (`config/business_rules.yaml: kitchen_capacity.staff_roster`), not
  from real employee shifts — because employee/shift generation (Phase 4)
  doesn't exist yet. These will need recomputing once it does.
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

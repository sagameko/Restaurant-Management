"""Synthetic order and order-item generation.

Implements the demand/channel/staffing relationships required by the
project spec: day-of-week and weather-driven demand, daypart-skewed
channel mix, delivery commission and longer promised windows, and a
kitchen-load model where preparation time, missing-item probability and
refund probability all rise as the kitchen gets busier.

Kitchen/front-of-house staff counts are a fixed roster estimate by
daypart and weekday-type (`config/business_rules.yaml: kitchen_capacity`)
rather than being derived from real shifts, since Phase 4 (employees and
shifts) has not been implemented yet. `kitchen_load_ratio` and
`preparation_minutes` will need recomputing once real shift data exists.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from restaurant_ops.config import SimulationSettings
from restaurant_ops.ingestion.loader import compute_menu_item_food_costs
from restaurant_ops.ingestion.schemas import Ingredient, MenuItem, Recipe

_DELIVERY_CHANNELS = {"uber_eats", "doordash"}


def _staff_roster(weekend_flag: bool, daypart: str, business_rules: dict) -> tuple[int, int]:
    category = "weekend" if weekend_flag else "weekday"
    roster = business_rules["kitchen_capacity"]["staff_roster"][category][daypart]
    return roster["kitchen"], roster["front_of_house"]


def _promotion_lookup(business_rules: dict) -> dict[str, dict]:
    return {promo["name"]: promo for promo in business_rules["promotions"]["schedule"]}


def _daily_order_count(
    context_row: pd.Series,
    average_daily_orders: int,
    business_rules: dict,
    promotions_by_name: dict[str, dict],
    rng: np.random.Generator,
) -> int:
    demand_cfg = business_rules["demand"]
    weekday_name = context_row["day_name"].lower()
    multiplier = demand_cfg["weekday_multipliers"][weekday_name]

    temperature_c = context_row["temperature_c"]
    if temperature_c <= demand_cfg["weather"]["cold_threshold_c"]:
        multiplier *= demand_cfg["weather"]["cold_day_volume_multiplier"]
    elif temperature_c >= demand_cfg["weather"]["hot_threshold_c"]:
        multiplier *= demand_cfg["weather"]["hot_day_volume_multiplier"]

    if context_row["public_holiday_flag"]:
        multiplier *= demand_cfg["public_holiday_volume_multiplier"]
    if context_row["city_event_flag"]:
        multiplier *= demand_cfg["city_event_volume_multiplier"]

    promotion_name = context_row["promotion_name"]
    if pd.notna(promotion_name):
        multiplier *= promotions_by_name[promotion_name]["volume_multiplier"]

    mean_orders = average_daily_orders * multiplier
    return int(rng.poisson(mean_orders))


def _daypart_split(total_orders: int, weekend_flag: bool, business_rules: dict) -> tuple[int, int]:
    share_cfg = business_rules["demand"]["daypart_share"]
    dinner_share = share_cfg["dinner_base"] + (
        share_cfg["weekend_dinner_boost"] if weekend_flag else 0
    )
    dinner_share = min(dinner_share, 0.95)
    dinner_orders = round(total_orders * dinner_share)
    lunch_orders = total_orders - dinner_orders
    return lunch_orders, dinner_orders


def _order_timestamps(
    business_date: date, daypart_cfg: dict, count: int, rng: np.random.Generator
) -> list[datetime]:
    if count == 0:
        return []
    hours = rng.triangular(
        daypart_cfg["start_hour"], daypart_cfg["peak_hour"], daypart_cfg["end_hour"], size=count
    )
    timestamps = [
        datetime.combine(business_date, datetime.min.time()) + timedelta(hours=float(h))
        for h in hours
    ]
    return sorted(timestamps)


def _orders_in_time_window(timestamps: list[datetime]) -> list[int]:
    """Count of orders sharing the same (business_date, hour) bucket."""
    hour_buckets = [ts.hour for ts in timestamps]
    bucket_counts = pd.Series(hour_buckets).value_counts()
    return [int(bucket_counts[bucket]) for bucket in hour_buckets]


def _channel_probabilities(
    daypart: str, simulation_settings: SimulationSettings, business_rules: dict
) -> tuple[list[str], np.ndarray]:
    channels = list(simulation_settings.channels.keys())
    daypart_multipliers = business_rules["channels"]["daypart_multipliers"][daypart]
    adjusted = np.array(
        [
            simulation_settings.channels[ch].probability * daypart_multipliers.get(ch, 1.0)
            for ch in channels
        ]
    )
    return channels, adjusted / adjusted.sum()


def _menu_item_weight(
    item: MenuItem,
    daypart: str,
    temperature_c: float,
    is_delivery_channel: bool,
    business_rules: dict,
) -> float:
    weight = item.base_popularity_weight
    weight *= item.lunch_affinity if daypart == "lunch" else item.dinner_affinity

    weather_cfg = business_rules["demand"]["weather"]
    if temperature_c <= weather_cfg["cold_threshold_c"]:
        weight *= item.cold_weather_affinity
    elif temperature_c >= weather_cfg["hot_threshold_c"]:
        weight *= item.hot_weather_affinity

    if is_delivery_channel:
        weight *= item.delivery_affinity
    return weight


def _sample_basket(
    eligible_items: list[MenuItem],
    weights: np.ndarray,
    business_rules: dict,
    rng: np.random.Generator,
) -> list[tuple[str, int]]:
    demand_cfg = business_rules["demand"]
    counts = list(demand_cfg["items_per_order_weights"].keys())
    count_probs = np.array(list(demand_cfg["items_per_order_weights"].values()), dtype=float)
    count_probs /= count_probs.sum()

    item_count = min(int(rng.choice(counts, p=count_probs)), len(eligible_items))
    norm_weights = weights / weights.sum()
    chosen_idx = rng.choice(len(eligible_items), size=item_count, replace=False, p=norm_weights)

    repeat_probability = demand_cfg["repeat_item_probability"]
    basket: list[tuple[str, int]] = []
    for idx in chosen_idx:
        quantity = 2 if rng.random() < repeat_probability else 1
        basket.append((eligible_items[idx].menu_item_id, quantity))
    return basket


def _base_prep_minutes(item_prep_minutes: list[float]) -> float:
    if not item_prep_minutes:
        return 0.0
    slowest = max(item_prep_minutes)
    remainder = sum(item_prep_minutes) - slowest
    return slowest + 0.4 * remainder


def _sample_status(
    kitchen_load_ratio: float,
    missing_item_flag: bool,
    late_flag: bool,
    business_rules: dict,
    rng: np.random.Generator,
) -> str:
    service_cfg = business_rules["service"]
    load_excess = max(0.0, kitchen_load_ratio - 1.0)

    p_cancelled = service_cfg["base_cancelled_prob"]
    p_partial_refund = (
        service_cfg["base_partial_refund_prob"]
        + service_cfg["refund_load_slope"] * load_excess
        + (service_cfg["missing_item_refund_boost"] if missing_item_flag else 0.0)
        + (service_cfg["late_order_refund_boost"] if late_flag else 0.0)
    )
    p_partial_refund = min(p_partial_refund, 0.6)
    p_completed = max(0.0, 1.0 - p_cancelled - p_partial_refund)

    probabilities = np.array([p_completed, p_cancelled, p_partial_refund])
    probabilities /= probabilities.sum()
    return str(rng.choice(["Completed", "Cancelled", "Partially Refunded"], p=probabilities))


def _customer_count(rng: np.random.Generator) -> int:
    return int(rng.choice([1, 2, 3, 4, 5, 6], p=[0.15, 0.35, 0.25, 0.15, 0.07, 0.03]))


def generate_orders_and_items(
    daily_context: pd.DataFrame,
    menu_items: list[MenuItem],
    ingredients: list[Ingredient],
    recipes: list[Recipe],
    simulation_settings: SimulationSettings,
    business_rules: dict,
    rng: np.random.Generator,
    average_daily_orders: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate the Orders and Order items tables for the whole simulation window."""
    menu_items_by_id = {item.menu_item_id: item for item in menu_items}
    food_cost_by_item = compute_menu_item_food_costs(ingredients, recipes).set_index(
        "menu_item_id"
    )["estimated_item_food_cost"]
    promotions_by_name = _promotion_lookup(business_rules)
    dayparts_cfg = business_rules["dayparts"]
    promised_minutes_cfg = business_rules["channels"]["promised_minutes"]
    service_cfg = business_rules["service"]
    capacity_per_staff_hour = business_rules["kitchen_capacity"][
        "capacity_per_kitchen_staff_per_hour"
    ]
    num_tables = max(1, simulation_settings.restaurant.seating_capacity // 4)
    delivery_eligible_items = [item for item in menu_items if item.available_for_delivery]
    average_daily_orders = (
        average_daily_orders or simulation_settings.simulation.average_daily_orders
    )

    order_rows: list[dict] = []
    order_item_rows: list[dict] = []
    order_counter = 0
    order_item_counter = 0

    for _, context_row in daily_context.iterrows():
        business_date = context_row["business_date"]
        weekend_flag = bool(context_row["weekend_flag"])
        temperature_c = float(context_row["temperature_c"])
        rain_mm = float(context_row["rain_mm"])
        promotion_name_today = context_row["promotion_name"]

        total_orders = _daily_order_count(
            context_row, average_daily_orders, business_rules, promotions_by_name, rng
        )
        lunch_count, dinner_count = _daypart_split(total_orders, weekend_flag, business_rules)

        for daypart, order_count in (("lunch", lunch_count), ("dinner", dinner_count)):
            if order_count == 0:
                continue

            kitchen_staff, foh_staff = _staff_roster(weekend_flag, daypart, business_rules)
            estimated_capacity = kitchen_staff * capacity_per_staff_hour
            channels, channel_probs = _channel_probabilities(
                daypart, simulation_settings, business_rules
            )

            timestamps = _order_timestamps(business_date, dayparts_cfg[daypart], order_count, rng)
            load_per_order = _orders_in_time_window(timestamps)

            for order_timestamp, orders_in_window in zip(timestamps, load_per_order, strict=True):
                order_counter += 1
                order_id = f"ORD{order_counter:06d}"

                channel = str(rng.choice(channels, p=channel_probs))
                is_delivery = channel in _DELIVERY_CHANNELS
                eligible_items = delivery_eligible_items if is_delivery else menu_items
                weights = np.array(
                    [
                        _menu_item_weight(item, daypart, temperature_c, is_delivery, business_rules)
                        for item in eligible_items
                    ]
                )
                basket = _sample_basket(eligible_items, weights, business_rules, rng)

                kitchen_load_ratio = orders_in_window / estimated_capacity

                item_prep_minutes = [
                    menu_items_by_id[menu_item_id].estimated_prep_minutes
                    for menu_item_id, _ in basket
                ]
                base_prep = _base_prep_minutes(item_prep_minutes)
                preparation_minutes = max(
                    service_cfg["min_preparation_minutes"],
                    base_prep
                    * (
                        1
                        + service_cfg["load_penalty_prep_slope"] * max(0.0, kitchen_load_ratio - 1)
                    )
                    + rng.normal(0, service_cfg["prep_time_noise_std_minutes"]),
                )
                promised_minutes = promised_minutes_cfg[channel]
                effective_minutes = preparation_minutes
                if is_delivery:
                    transit_minutes = max(
                        0.0,
                        rng.normal(
                            service_cfg["delivery_transit_minutes_mean"],
                            service_cfg["delivery_transit_minutes_std"],
                        ),
                    )
                    effective_minutes += transit_minutes
                late_flag = effective_minutes > promised_minutes

                missing_item_prob = service_cfg["base_missing_item_prob"] + service_cfg[
                    "missing_item_load_slope"
                ] * max(0.0, kitchen_load_ratio - 1)
                missing_item_flag = rng.random() < missing_item_prob
                missing_item_idx = rng.integers(0, len(basket)) if missing_item_flag else None

                status = _sample_status(
                    kitchen_load_ratio, missing_item_flag, late_flag, business_rules, rng
                )

                promo_redeemed = (
                    pd.notna(promotion_name_today)
                    and rng.random() < business_rules["promotions"]["redemption_rate"]
                )

                subtotal = 0.0
                estimated_food_cost = 0.0
                item_dicts = []
                for item_idx, (menu_item_id, quantity) in enumerate(basket):
                    menu_item = menu_items_by_id[menu_item_id]
                    unit_food_cost = float(food_cost_by_item[menu_item_id])
                    line_total = menu_item.selling_price * quantity
                    line_food_cost = unit_food_cost * quantity
                    subtotal += line_total
                    estimated_food_cost += line_food_cost

                    special_request = None
                    if rng.random() < service_cfg["special_request_probability"]:
                        special_request = str(rng.choice(service_cfg["special_requests"]))

                    order_item_counter += 1
                    item_dicts.append(
                        {
                            "order_item_id": f"OI{order_item_counter:07d}",
                            "order_id": order_id,
                            "menu_item_id": menu_item_id,
                            "quantity": quantity,
                            "unit_price": menu_item.selling_price,
                            "estimated_unit_food_cost": round(unit_food_cost, 4),
                            "line_total": round(line_total, 2),
                            "estimated_line_food_cost": round(line_food_cost, 4),
                            "special_request": special_request,
                            "item_status": "Missing"
                            if item_idx == missing_item_idx
                            else "Fulfilled",
                        }
                    )

                discount_amount = 0.0
                order_promotion_name = None
                if promo_redeemed:
                    order_promotion_name = promotion_name_today
                    discount_amount = (
                        subtotal * promotions_by_name[promotion_name_today]["discount_pct"]
                    )

                commission_rate = simulation_settings.channels[channel].commission_rate
                platform_commission = (
                    0.0 if status == "Cancelled" else (subtotal - discount_amount) * commission_rate
                )

                if status == "Cancelled":
                    refund_amount = subtotal - discount_amount
                elif status == "Partially Refunded":
                    fraction = rng.uniform(*service_cfg["partial_refund_fraction_range"])
                    refund_amount = (subtotal - discount_amount) * fraction
                else:
                    refund_amount = 0.0

                net_sales = subtotal - discount_amount - refund_amount - platform_commission
                estimated_gross_profit = net_sales - estimated_food_cost

                is_dine_in = channel == "dine_in"
                order_rows.append(
                    {
                        "order_id": order_id,
                        "order_timestamp": order_timestamp,
                        "business_date": business_date,
                        "daypart": daypart,
                        "channel": channel,
                        "status": status,
                        "table_number": int(rng.integers(1, num_tables + 1))
                        if is_dine_in
                        else None,
                        "customer_count": _customer_count(rng) if is_dine_in else None,
                        "promotion_name": order_promotion_name,
                        "subtotal": round(subtotal, 2),
                        "discount_amount": round(discount_amount, 2),
                        "refund_amount": round(refund_amount, 2),
                        "platform_commission": round(platform_commission, 2),
                        "net_sales": round(net_sales, 2),
                        "estimated_food_cost": round(estimated_food_cost, 4),
                        "estimated_gross_profit": round(estimated_gross_profit, 4),
                        "preparation_minutes": round(preparation_minutes, 1),
                        "promised_minutes": float(promised_minutes),
                        "late_flag": late_flag,
                        "missing_item_flag": missing_item_flag,
                        "kitchen_staff_count": kitchen_staff,
                        "front_of_house_staff_count": foh_staff,
                        "kitchen_load_ratio": round(kitchen_load_ratio, 3),
                        "temperature_c": temperature_c,
                        "rain_mm": rain_mm,
                    }
                )
                order_item_rows.extend(item_dicts)

    orders_df = pd.DataFrame(order_rows)
    order_items_df = pd.DataFrame(order_item_rows)
    return orders_df, order_items_df

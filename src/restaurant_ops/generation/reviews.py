"""Synthetic customer-review generation.

Ratings are derived from operational outcomes (late orders, missing
items, severe kitchen delays) plus random noise, not `random.randint(1, 5)`,
per the project spec. Review text is drawn from a small set of
hand-written, clearly-synthetic templates keyed by rating band.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

_ELIGIBLE_STATUSES = {"Completed", "Partially Refunded"}
_NEGATIVE_COMPLAINT_CATEGORIES = ["Food Quality", "Order Accuracy", "Customer Service"]


def _rating_for_order(order: pd.Series, reviews_cfg: dict, rng: np.random.Generator) -> int:
    rating_score = reviews_cfg["base_rating"]
    if order["late_flag"]:
        rating_score -= reviews_cfg["late_penalty"]
    if order["missing_item_flag"]:
        rating_score -= reviews_cfg["missing_item_penalty"]
    if (
        order["preparation_minutes"]
        > order["promised_minutes"] + reviews_cfg["severe_delay_extra_minutes"]
    ):
        rating_score -= reviews_cfg["severe_delay_penalty"]
    rating_score += rng.normal(0, reviews_cfg["noise_std"])
    rating_score = min(5.0, max(1.0, rating_score))
    return int(round(rating_score))


def _complaint_category(order: pd.Series, rating: int, rng: np.random.Generator) -> str | None:
    if order["missing_item_flag"]:
        return "Missing Item"
    if order["late_flag"]:
        return "Late Order"
    if rating <= 2:
        return str(rng.choice(_NEGATIVE_COMPLAINT_CATEGORIES))
    return None


def _review_text(rating: int, templates: dict, rng: np.random.Generator) -> str:
    if rating >= 4:
        bucket = templates["positive"]
    elif rating == 3:
        bucket = templates["neutral"]
    else:
        bucket = templates["negative"]
    return str(rng.choice(bucket))


def generate_reviews(
    orders: pd.DataFrame, simulation_end_date, business_rules: dict, rng: np.random.Generator
) -> pd.DataFrame:
    """Sample a subset of eligible orders and generate a review for each.

    Cancelled orders are excluded — a customer who never received food
    has nothing to rate. Every review is clearly synthetic: templated
    text and a formula-driven rating, never `random.randint(1, 5)`.
    """
    reviews_cfg = business_rules["reviews"]
    review_probability_by_channel = reviews_cfg["probability_by_channel"]
    offset_min, offset_max = reviews_cfg["review_date_offset_days"]

    review_rows: list[dict] = []
    review_counter = 0

    for _, order in orders.iterrows():
        if order["status"] not in _ELIGIBLE_STATUSES:
            continue
        if rng.random() >= review_probability_by_channel[order["channel"]]:
            continue

        rating = _rating_for_order(order, reviews_cfg, rng)
        complaint_category = _complaint_category(order, rating, rng)
        review_date = order["business_date"] + timedelta(
            days=int(rng.integers(offset_min, offset_max + 1))
        )
        review_date = min(review_date, simulation_end_date)

        review_counter += 1
        review_rows.append(
            {
                "review_id": f"REV{review_counter:06d}",
                "order_id": order["order_id"],
                "review_date": review_date,
                "channel": order["channel"],
                "rating": rating,
                "review_text": _review_text(rating, reviews_cfg["templates"], rng),
                "complaint_category": complaint_category,
                "response_required_flag": rating <= 2 or complaint_category is not None,
            }
        )

    return pd.DataFrame(review_rows)

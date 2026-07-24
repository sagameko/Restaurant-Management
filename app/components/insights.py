"""Small rule-based text summaries.

Pure functions (no Streamlit imports) so the logic is testable independent
of the UI: give them an already-loaded DataFrame, get a sentence back.
"""

from __future__ import annotations

import pandas as pd


def daily_performance_summary(prep_vs_promised: pd.DataFrame) -> str:
    """Summarise the busiest (day, daypart) slot and how prep time compared
    to its promised-time target.

    `prep_vs_promised` is the output of
    `app.components.database.prep_time_vs_promised_by_daypart()`:
    columns `day_name`, `daypart`, `order_count`, `avg_preparation_minutes`,
    `avg_promised_minutes`.
    """
    if prep_vs_promised.empty:
        return "Not enough data to generate a summary yet."

    busiest = prep_vs_promised.loc[prep_vs_promised["order_count"].idxmax()]
    variance = busiest["avg_preparation_minutes"] - busiest["avg_promised_minutes"]
    slot = f"{busiest['day_name']} {busiest['daypart'].lower()}"

    if variance > 0.5:
        return (
            f"{slot} produced the highest order volume, but average "
            f"preparation time exceeded the target by {variance:.1f} minutes."
        )
    if variance < -0.5:
        return (
            f"{slot} produced the highest order volume, and average "
            f"preparation time beat the target by {abs(variance):.1f} minutes."
        )
    return (
        f"{slot} produced the highest order volume, right at the promised preparation-time target."
    )

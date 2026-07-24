"""Time-based train/test splitting and forecast-error metrics.

Never randomly split time-series data — the split here is strictly
chronological, matching the spec requirement.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def time_based_split(df: pd.DataFrame, test_days: int = 60) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a chronologically-sorted feature frame into train/test.

    The last `test_days` rows (by `business_date`) become the test set;
    everything before that is train. Assumes `df` is already sorted by
    `business_date` (true of `build_feature_frame`'s output).
    """
    if test_days >= len(df):
        raise ValueError(f"test_days ({test_days}) must be smaller than the frame ({len(df)} rows)")
    train = df.iloc[:-test_days].reset_index(drop=True)
    test = df.iloc[-test_days:].reset_index(drop=True)
    return train, test


def mae(actual: pd.Series, predicted: pd.Series) -> float:
    return float(np.mean(np.abs(np.asarray(actual) - np.asarray(predicted))))


def rmse(actual: pd.Series, predicted: pd.Series) -> float:
    return float(np.sqrt(np.mean((np.asarray(actual) - np.asarray(predicted)) ** 2)))


def mape(actual: pd.Series, predicted: pd.Series) -> float:
    """Mean absolute percentage error, as a percentage (0-100 scale)."""
    actual_arr = np.asarray(actual, dtype=float)
    predicted_arr = np.asarray(predicted, dtype=float)
    return float(np.mean(np.abs((actual_arr - predicted_arr) / actual_arr)) * 100)

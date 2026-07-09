from __future__ import annotations

from typing import Any

import pandas as pd


def seconds(value: Any) -> float:
    """Convert pandas/NumPy/Python timedelta-like values to seconds."""

    if value is None or pd.isna(value):
        return float("nan")
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds())
    return float(pd.to_timedelta(value).total_seconds())


def add_seconds_column(
    frame: pd.DataFrame,
    source: str,
    target: str,
) -> pd.DataFrame:
    """Return a copy with a numeric seconds column derived from a timedelta column."""

    result = frame.copy()
    if source in result.columns:
        result[target] = pd.to_timedelta(result[source]).dt.total_seconds()
    return result

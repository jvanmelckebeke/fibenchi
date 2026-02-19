"""Shared utility functions for compute modules."""

import pandas as pd

from app.models import PriceHistory


def prices_to_df(prices: list[PriceHistory]) -> pd.DataFrame:
    """Convert a list of PriceHistory ORM objects to a pandas DataFrame.

    Returns a DataFrame indexed by date with columns: open, high, low, close, volume.
    """
    return pd.DataFrame([{
        "date": p.date,
        "open": p.open,
        "high": p.high,
        "low": p.low,
        "close": p.close,
        "volume": p.volume,
    } for p in prices]).set_index("date")

"""Shared utility functions for compute modules."""

import pandas as pd

from app.models import PriceHistory


def prices_to_df(prices: list[PriceHistory]) -> pd.DataFrame:
    """Convert a list of PriceHistory ORM objects to a pandas DataFrame.

    Returns a DataFrame indexed by date with columns: open, high, low, close,
    volume, dividends.

    ``dividends`` keeps the provider's plural name so a stored frame and a
    freshly fetched one are the same shape — the ephemeral price path feeds
    provider frames straight into ``compute_indicators``. A null stored
    dividend becomes 0.0: for the total-return numerator, "unknown" and "none"
    both mean there is no cash to add back.
    """
    return pd.DataFrame([{
        "date": p.date,
        "open": p.open,
        "high": p.high,
        "low": p.low,
        "close": p.close,
        "volume": p.volume,
        "dividends": p.dividend or 0.0,
    } for p in prices]).set_index("date")

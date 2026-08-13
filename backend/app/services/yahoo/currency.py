"""Currency resolution and OHLCV normalization for Yahoo Finance data.

The suffix→currency table that used to live here merged into the one venue
table in ``app.services.market_calendar`` (``SUFFIX_LISTINGS``); ticker-shape
currency inference is ``AssetRef(symbol).currency``.
"""

import pandas as pd

from app.domain import AssetRef
from app.services.currency_service import lookup as currency_lookup


def resolve_currency(info: dict, symbol: str) -> tuple[str, int]:
    """Resolve display currency and subunit divisor from Yahoo price info.

    Applies the standard fallback chain:
      1. Extract raw currency from the price info dict
      2. Look it up in the currency cache (handles subunits like GBp -> GBP/100)
      3. Fall back to the ticker's venue currency (Symbol.currency)
      4. Default to ("USD", 1)

    Returns (display_code, divisor).
    """
    raw = info.get("currency") if isinstance(info, dict) else None
    if raw:
        return currency_lookup(raw)
    venue_currency = AssetRef(symbol).currency
    if venue_currency:
        return (venue_currency, 1)
    return ("USD", 1)


def _normalize_ohlcv_df(df: pd.DataFrame, divisor: int) -> pd.DataFrame:
    """Divide OHLCV price columns by divisor. Volume is left unchanged."""
    if divisor == 1:
        return df
    price_cols = [c for c in ("open", "high", "low", "close", "adjclose") if c in df.columns]
    df = df.copy()
    df[price_cols] = df[price_cols] / divisor
    return df

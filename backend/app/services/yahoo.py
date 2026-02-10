"""Yahoo Finance data fetching via yahooquery."""

from datetime import date

import pandas as pd
from yahooquery import Ticker

PERIOD_MAP = {
    "1d": "1d", "5d": "5d", "1w": "5d",
    "1mo": "1mo", "3mo": "3mo", "6mo": "6mo",
    "1y": "1y", "2y": "2y", "5y": "5y",
    "ytd": "ytd", "max": "max",
}


def fetch_history(
    symbol: str,
    period: str = "3mo",
    interval: str = "1d",
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Fetch OHLCV data from Yahoo Finance.

    Returns DataFrame with columns: open, high, low, close, volume.
    Index: date.
    """
    ticker = Ticker(symbol)

    if start and end:
        df = ticker.history(start=str(start), end=str(end), interval=interval)
    else:
        normalized = PERIOD_MAP.get(period.lower(), period)
        df = ticker.history(period=normalized, interval=interval)

    if isinstance(df, dict) or df.empty:
        raise ValueError(f"No data found for {symbol}")

    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index().set_index("date")

    return df


def validate_symbol(symbol: str) -> dict | None:
    """Validate a ticker and return basic info, or None if invalid."""
    ticker = Ticker(symbol)
    quote = ticker.quote_type.get(symbol, {})

    if not quote or isinstance(quote, str):
        return None

    return {
        "symbol": symbol.upper(),
        "name": quote.get("shortName") or quote.get("longName") or symbol.upper(),
        "type": quote.get("quoteType", "EQUITY"),
    }


def batch_fetch_history(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Fetch history for multiple symbols in one batch call."""
    if not symbols:
        return {}

    ticker = Ticker(symbols)
    normalized = PERIOD_MAP.get(period.lower(), period)
    hist = ticker.history(period=normalized, interval="1d")

    if isinstance(hist, dict) or hist.empty:
        return {}

    result = {}
    for sym in symbols:
        try:
            if isinstance(hist.index, pd.MultiIndex):
                df = hist.loc[sym].copy()
            else:
                df = hist.copy()
            if not df.empty and len(df) >= 2:
                result[sym] = df
        except KeyError:
            continue

    return result

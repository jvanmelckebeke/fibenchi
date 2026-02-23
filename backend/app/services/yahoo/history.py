"""Yahoo Finance OHLCV history fetching."""

from datetime import date

import pandas as pd
from yahooquery import Ticker

from app.services.yahoo.currency import _normalize_ohlcv_df, resolve_currency
from app.utils import async_threadable

PERIOD_MAP = {
    "1d": "1d", "5d": "5d", "1w": "5d",
    "1mo": "1mo", "3mo": "3mo", "6mo": "6mo",
    "1y": "1y", "2y": "2y", "5y": "5y",
    "ytd": "ytd", "max": "max",
}


@async_threadable
def fetch_history(
    symbol: str,
    period: str = "3mo",
    interval: str = "1d",
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Fetch OHLCV data from Yahoo Finance.

    Returns DataFrame with columns: open, high, low, close, volume.
    Index: date. Subunit currencies (e.g. GBp) are converted to main units.
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

    # Convert subunit prices (e.g. pence -> pounds)
    price_info = ticker.price.get(symbol, {})
    _, divisor = resolve_currency(price_info, symbol)
    df = _normalize_ohlcv_df(df, divisor)

    return df


def _batch_fetch_history_sync(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Sync implementation of batch history fetch (used by other sync Yahoo helpers)."""
    if not symbols:
        return {}

    ticker = Ticker(symbols)
    price_data = ticker.price
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
                # Convert subunit prices (e.g. pence -> pounds)
                info = price_data.get(sym, {}) if isinstance(price_data, dict) else {}
                _, divisor = resolve_currency(info, sym)
                df = _normalize_ohlcv_df(df, divisor)
                result[sym] = df
        except KeyError:
            continue

    return result


@async_threadable
def batch_fetch_history(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Fetch history for multiple symbols in one batch call.

    Subunit currencies (e.g. GBp) are converted to main units.
    This is the async version -- use ``_batch_fetch_history_sync`` for
    calls from within other sync Yahoo helpers running in a thread.
    """
    return _batch_fetch_history_sync(symbols, period=period)

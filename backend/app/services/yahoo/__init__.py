"""Yahoo Finance data fetching via yahooquery.

This package splits Yahoo Finance operations into focused modules:
- currency: Exchange suffix mapping, currency resolution, OHLCV normalization
- history: Single and batch OHLCV history fetching
- quotes: Real-time quote fetching and currency batch lookup
- validation: Symbol validation and type detection
- holdings: ETF top holdings and sector weightings
- search: Yahoo Finance symbol search

All public functions are re-exported here so consumers can continue to use:
    from app.services.yahoo import <name>
"""

from app.services.yahoo.currency import (
    EXCHANGE_CURRENCY_MAP,
    _normalize_ohlcv_df,
    currency_from_suffix,
    resolve_currency,
)
from app.services.yahoo.history import (
    PERIOD_MAP,
    _batch_fetch_history_sync,
    batch_fetch_history,
    fetch_history,
)
from app.services.yahoo.holdings import (
    _holdings_cache,
    fetch_etf_holdings,
)
from app.services.yahoo.quotes import (
    batch_fetch_currencies,
    batch_fetch_quotes,
)
from app.services.yahoo.search import search
from app.services.yahoo.validation import validate_symbol

__all__ = [
    # currency
    "EXCHANGE_CURRENCY_MAP",
    "currency_from_suffix",
    "resolve_currency",
    "_normalize_ohlcv_df",
    # history
    "PERIOD_MAP",
    "fetch_history",
    "_batch_fetch_history_sync",
    "batch_fetch_history",
    # quotes
    "batch_fetch_quotes",
    "batch_fetch_currencies",
    # validation
    "validate_symbol",
    # holdings
    "fetch_etf_holdings",
    "_holdings_cache",
    # search
    "search",
]

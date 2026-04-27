"""Yahoo Finance data fetching.

All Yahoo HTTP access goes through :data:`yahoo_client` (a
:class:`YahooClient` instance) — that single object owns the throttle,
circuit breaker, quote/holdings caches, and retry policy.

Direct ``from yahooquery import Ticker`` imports outside this package are
a code smell; route the call through ``yahoo_client.<method>(...)`` instead.

The pure-mapping helpers (currency suffix table, OHLCV normalisation,
period mapping) are re-exported here for convenience since they have no
Yahoo I/O concerns.
"""

from app.services.yahoo._parsers import PERIOD_MAP
from app.services.yahoo.client import (
    YahooClient,
    yahoo_client,
)
from app.services.yahoo.currency import (
    EXCHANGE_CURRENCY_MAP,
    _normalize_ohlcv_df,
    currency_from_suffix,
    resolve_currency,
)

__all__ = [
    "YahooClient",
    "yahoo_client",
    "PERIOD_MAP",
    "EXCHANGE_CURRENCY_MAP",
    "currency_from_suffix",
    "resolve_currency",
    "_normalize_ohlcv_df",
]

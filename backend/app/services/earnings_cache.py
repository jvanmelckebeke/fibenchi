"""Earnings date cache with 24h TTL.

Caches per-symbol earnings date lookups so the asset detail page
doesn't hit Yahoo Finance on every load.
"""

import logging

from app.services.yahoo.earnings import fetch_earnings_date
from app.utils import TTLCache

logger = logging.getLogger(__name__)

_earnings_cache: TTLCache = TTLCache(default_ttl=86400, max_size=500, thread_safe=True)


async def get_earnings(symbol: str) -> dict[str, object] | None:
    """Return earnings date for symbol, using cache when available."""
    upper = symbol.upper()
    cached = _earnings_cache.get_value(upper)
    if cached is not None:
        return cached

    result = await fetch_earnings_date(upper)
    if result is not None:
        _earnings_cache.set_value(upper, result)
    return result

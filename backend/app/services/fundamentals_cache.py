"""Shared fundamentals cache with background refresh.

Yahoo Finance fundamental metrics (Forward P/E, PEG, ROE, etc.) are slow to
fetch (~9s for 25 symbols) but change at most daily.  This module provides a
24-hour TTL cache so indicator endpoints return instantly and fundamentals are
merged from cache when available.
"""

import asyncio
import logging

from app.services.yahoo import batch_fetch_fundamentals
from app.utils import TTLCache

logger = logging.getLogger(__name__)

# Per-symbol fundamentals cache: keyed by uppercase symbol, value is
# dict[field, value].  24h TTL since fundamentals change at most daily.
_fundamentals_cache: TTLCache = TTLCache(default_ttl=86400, max_size=500)

# Track in-flight background fetches to avoid duplicate work
_pending_symbols: set[str] = set()


def get_cached_fundamentals(symbols: list[str]) -> dict[str, dict[str, float | None]]:
    """Return cached fundamentals for the given symbols.

    Only symbols that have a cache entry are included in the result.
    Missing symbols are silently omitted.
    """
    result: dict[str, dict[str, float | None]] = {}
    for sym in symbols:
        cached = _fundamentals_cache.get_value(sym.upper())
        if cached is not None:
            result[sym.upper()] = cached
    return result


def get_uncached_symbols(symbols: list[str]) -> list[str]:
    """Return symbols that are NOT in the cache."""
    return [s for s in symbols if _fundamentals_cache.get_value(s.upper()) is None]


async def warm_fundamentals_cache(symbols: list[str]) -> None:
    """Fetch and cache fundamentals for the given symbols (blocking).

    Called during scheduled refresh to pre-warm the cache.
    """
    if not symbols:
        return
    try:
        data = await batch_fetch_fundamentals(symbols)
        for sym, metrics in data.items():
            clean = {k: v for k, v in metrics.items() if v is not None}
            if clean:
                _fundamentals_cache.set_value(sym.upper(), clean)
        logger.info("Warmed fundamentals cache for %d symbols", len(data))
    except Exception:
        logger.exception("Failed to warm fundamentals cache")


def _schedule_background_fetch(symbols: list[str]) -> None:
    """Fire-and-forget background fetch for uncached symbols.

    Prevents duplicate fetches for the same symbols.
    """
    to_fetch = [s for s in symbols if s.upper() not in _pending_symbols]
    if not to_fetch:
        return

    for s in to_fetch:
        _pending_symbols.add(s.upper())

    async def _fetch():
        try:
            data = await batch_fetch_fundamentals(to_fetch)
            for sym, metrics in data.items():
                clean = {k: v for k, v in metrics.items() if v is not None}
                if clean:
                    _fundamentals_cache.set_value(sym.upper(), clean)
        except Exception:
            logger.exception("Background fundamentals fetch failed")
        finally:
            for s in to_fetch:
                _pending_symbols.discard(s.upper())

    asyncio.create_task(_fetch())


def merge_fundamentals_from_cache(
    symbols: list[str],
    target: dict[str, dict],
    values_key: str = "values",
) -> None:
    """Merge cached fundamentals into target dict, scheduling background fetch for misses.

    For each symbol in target, if fundamentals are cached, merge them into
    target[symbol][values_key].  Symbols without cache entries trigger a
    background fetch so they'll be available on the next request.
    """
    cached = get_cached_fundamentals(symbols)
    uncached = []

    for sym in symbols:
        upper = sym.upper()
        fund = cached.get(upper)
        if fund and sym in target:
            target[sym].setdefault(values_key, {}).update(fund)
        elif upper not in cached:
            uncached.append(upper)

    if uncached:
        _schedule_background_fetch(uncached)


def merge_fundamentals_into_rows(symbol: str, rows: list) -> None:
    """Merge cached fundamentals into the last indicator row.

    Schedules a background fetch if the symbol is not cached.
    """
    upper = symbol.upper()
    cached = _fundamentals_cache.get_value(upper)
    if cached and rows:
        rows[-1].values.update(cached)
    elif cached is None:
        _schedule_background_fetch([upper])


def merge_fundamentals_into_batch(results: list[dict]) -> None:
    """Merge cached fundamentals into batch indicator snapshots.

    Each entry in results has a 'symbol' key. Schedules background fetch
    for any symbols not in cache.
    """
    symbols = [e["symbol"] for e in results if "symbol" in e]
    cached = get_cached_fundamentals(symbols)
    uncached = []

    for entry in results:
        sym = entry.get("symbol", "").upper()
        fund = cached.get(sym)
        if fund:
            entry.setdefault("values", {}).update(fund)
        elif sym and sym not in cached:
            uncached.append(sym)

    if uncached:
        _schedule_background_fetch(uncached)

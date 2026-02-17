"""Search business logic — symbol search with TTL cache."""

import time

from app.services.yahoo import search as yahoo_search

# Simple TTL cache: query -> (results, timestamp)
_cache: dict[str, tuple[list, float]] = {}
_CACHE_TTL = 300  # 5 minutes
_CACHE_MAX = 200  # evict oldest when exceeded


def _get_cached(q: str) -> list | None:
    entry = _cache.get(q)
    if entry and time.monotonic() - entry[1] < _CACHE_TTL:
        return entry[0]
    return None


def _put_cache(q: str, results: list) -> None:
    if len(_cache) >= _CACHE_MAX:
        oldest = min(_cache, key=lambda k: _cache[k][1])
        del _cache[oldest]
    _cache[q] = (results, time.monotonic())


async def search_symbols(query: str) -> list[dict]:
    """Search for ticker symbols, returning up to 8 equity/ETF matches."""
    q_lower = query.strip().lower()
    cached = _get_cached(q_lower)
    if cached is not None:
        return cached

    raw = await yahoo_search(q_lower, first_quote=False)
    quotes = raw.get("quotes", [])

    results = []
    for item in quotes:
        qt = item.get("quoteType", "")
        if qt not in ("EQUITY", "ETF"):
            continue
        results.append({
            "symbol": item.get("symbol", ""),
            "name": item.get("shortname") or item.get("longname") or "",
            "exchange": item.get("exchDisp") or item.get("exchange") or "",
            "type": "stock" if qt == "EQUITY" else "etf",
        })
        if len(results) >= 8:
            break

    _put_cache(q_lower, results)
    return results

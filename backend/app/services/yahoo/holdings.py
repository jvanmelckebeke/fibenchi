"""Yahoo Finance ETF holdings and sector weightings."""

from yahooquery import Ticker

from app.utils import TTLCache, async_threadable

# In-memory TTL cache for ETF holdings (holdings change quarterly at most)
_holdings_cache: TTLCache = TTLCache(default_ttl=86400, max_size=100, thread_safe=True)


@async_threadable
def fetch_etf_holdings(symbol: str) -> dict | None:
    """Fetch ETF top holdings and sector weightings from Yahoo Finance.

    Results are cached in-memory for 24h since holdings change quarterly at most.
    Returns None if the symbol is not an ETF or data is unavailable.
    """
    key = symbol.upper()
    cached = _holdings_cache.get_value(key)
    if cached is not None:
        return cached

    result = _fetch_etf_holdings_uncached(symbol)
    _holdings_cache.set_value(key, result)

    return result


def _fetch_etf_holdings_uncached(symbol: str) -> dict | None:
    """Actual Yahoo Finance fetch for ETF holdings (no cache)."""
    ticker = Ticker(symbol)
    info = ticker.fund_holding_info.get(symbol)

    if not info or isinstance(info, str):
        return None

    holdings = []
    for h in info.get("holdings", []):
        holdings.append({
            "symbol": h.get("symbol", ""),
            "name": h.get("holdingName", ""),
            "percent": round(h.get("holdingPercent", 0) * 100, 2),
        })

    sector_map = {
        "realestate": "Real Estate",
        "consumer_cyclical": "Consumer Cyclical",
        "basic_materials": "Basic Materials",
        "consumer_defensive": "Consumer Defensive",
        "technology": "Technology",
        "communication_services": "Communication Services",
        "financial_services": "Financial Services",
        "utilities": "Utilities",
        "industrials": "Industrials",
        "energy": "Energy",
        "healthcare": "Healthcare",
    }

    sectors = []
    for entry in info.get("sectorWeightings", []):
        for key, val in entry.items():
            pct = round(val * 100, 2)
            if pct > 0:
                sectors.append({
                    "sector": sector_map.get(key, key),
                    "percent": pct,
                })
    sectors.sort(key=lambda s: s["percent"], reverse=True)

    total = round(sum(h["percent"] for h in holdings), 2)

    return {
        "top_holdings": holdings,
        "sector_weightings": sectors,
        "total_percent": total,
    }

import asyncio

from fastapi import APIRouter, Query
from yahooquery import search as yq_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search_symbols(q: str = Query(..., min_length=1, max_length=50)):
    """Search for ticker symbols by name or symbol prefix."""
    raw = await asyncio.to_thread(yq_search, q, first_quote=False)
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

    return results

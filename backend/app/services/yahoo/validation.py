"""Yahoo Finance symbol validation and type detection."""

from yahooquery import Ticker

from app.services.currency_service import lookup as currency_lookup
from app.services.yahoo.currency import currency_from_suffix
from app.utils import async_threadable


@async_threadable
def validate_symbol(symbol: str) -> dict | None:
    """Validate a ticker and return basic info, or None if invalid.

    Returns both ``currency`` (display code for API responses) and
    ``currency_code`` (raw Yahoo code for DB storage).
    """
    ticker = Ticker(symbol)
    quote = ticker.quote_type.get(symbol, {})

    if not quote or isinstance(quote, str):
        return None

    # Extract raw currency from Yahoo data sources
    price_info = ticker.price.get(symbol, {})
    raw_code = None
    if isinstance(price_info, dict):
        raw_code = price_info.get("currency")
    if not raw_code:
        detail = ticker.summary_detail.get(symbol, {})
        if isinstance(detail, dict):
            raw_code = detail.get("currency")
    if not raw_code:
        raw_code = currency_from_suffix(symbol) or "USD"

    display_code, _ = currency_lookup(raw_code)

    return {
        "symbol": symbol.upper(),
        "name": quote.get("shortName") or quote.get("longName") or symbol.upper(),
        "type": quote.get("quoteType", "EQUITY"),
        "currency": display_code,
        "currency_code": raw_code,
    }

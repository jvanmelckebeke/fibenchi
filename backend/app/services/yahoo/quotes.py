"""Yahoo Finance real-time quote fetching."""

import logging
import math

from yahooquery import Ticker

from app.services.yahoo.currency import resolve_currency
from app.utils import async_threadable

logger = logging.getLogger(__name__)


def _sanitize(val: float | None) -> float | None:
    """Convert NaN/Infinity to None so json.dumps produces valid JSON."""
    if val is None:
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    return val


def _parse_price_data(
    ticker: Ticker,
    symbols: list[str],
    price_data: dict,
) -> list[dict]:
    """Build quote dicts from Yahoo price data, with NaN sanitization and logging."""
    results = []
    null_symbols: list[str] = []
    nan_fields: list[str] = []

    for sym in symbols:
        info = price_data.get(sym, {})
        if not isinstance(info, dict):
            logger.warning("Yahoo returned non-dict for %s: %s", sym, repr(info)[:200])
            results.append({"symbol": sym})
            continue

        currency, divisor = resolve_currency(info, sym)

        price = _sanitize(info.get("regularMarketPrice"))
        prev_close = _sanitize(info.get("regularMarketPreviousClose"))
        change = _sanitize(info.get("regularMarketChange"))
        change_pct = _sanitize(info.get("regularMarketChangePercent"))
        volume = info.get("regularMarketVolume")
        avg_volume = info.get("averageDailyVolume10Day")

        if price is None and info.get("regularMarketPrice") is not None:
            nan_fields.append(f"{sym}.price")
        if change_pct is None and info.get("regularMarketChangePercent") is not None:
            nan_fields.append(f"{sym}.change_percent")

        if price is None and change_pct is None and info.get("marketState") is None:
            null_symbols.append(sym)

        results.append({
            "symbol": sym,
            "price": round(float(price) / divisor, 4) if price is not None else None,
            "previous_close": round(float(prev_close) / divisor, 4) if prev_close is not None else None,
            "change": round(float(change) / divisor, 4) if change is not None else None,
            "change_percent": round(float(change_pct) * 100, 2) if change_pct is not None else None,
            "volume": int(volume) if volume is not None else None,
            "avg_volume": int(avg_volume) if avg_volume is not None else None,
            "currency": currency,
            "market_state": info.get("marketState"),
        })

    if nan_fields:
        logger.warning("Yahoo returned NaN/Infinity for: %s", ", ".join(nan_fields))
    if null_symbols:
        logger.warning(
            "Yahoo returned all-null data for %d/%d symbols: %s — "
            "possible rate-limiting or auth issue",
            len(null_symbols), len(symbols), ", ".join(null_symbols[:10]),
        )

    return results


def _has_invalid_crumb(price_data: dict) -> bool:
    """Check if Yahoo rejected the crumb for all symbols."""
    return all(
        isinstance(v, str) and "Invalid Crumb" in v
        for v in price_data.values()
    ) if price_data else False


@async_threadable
def batch_fetch_quotes(symbols: list[str]) -> list[dict]:
    """Fetch current market quotes for multiple symbols in one batch call.

    Returns a list of dicts with keys: symbol, price, previous_close, change,
    change_percent, currency, market_state.
    """
    if not symbols:
        return []

    ticker = Ticker(symbols)
    price_data = ticker.price

    # Retry once with a fresh session if Yahoo rejected the crumb
    if _has_invalid_crumb(price_data):
        logger.warning(
            "Yahoo rejected crumb for all %d symbols — retrying with fresh session",
            len(symbols),
        )
        ticker = Ticker(symbols)
        price_data = ticker.price
        if _has_invalid_crumb(price_data):
            logger.error(
                "Yahoo crumb rejected twice — likely IP-level blocking. "
                "Consider restarting the container or using a proxy."
            )

    return _parse_price_data(ticker, symbols, price_data)


def batch_fetch_currencies(symbols: list[str]) -> dict[str, str]:
    """Fetch currencies for multiple symbols in one batch call.

    Returns a dict mapping symbol -> display currency code (e.g. "USD", "GBP").
    Subunit currencies (e.g. GBp) are normalized to their main currency via lookup.
    """
    if not symbols:
        return {}

    ticker = Ticker(symbols)
    price_data = ticker.price

    result = {}
    for sym in symbols:
        info = price_data.get(sym, {}) if isinstance(price_data, dict) else {}
        display, _ = resolve_currency(info, sym)
        result[sym] = display

    return result

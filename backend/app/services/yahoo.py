"""Yahoo Finance data fetching via yahooquery."""

import logging
import math
from datetime import date

import pandas as pd
from yahooquery import Ticker
from yahooquery import search as _yq_search

from app.services.currency_service import lookup as currency_lookup
from app.utils import TTLCache, async_threadable

logger = logging.getLogger(__name__)

# In-memory TTL cache for ETF holdings (holdings change quarterly at most)
_holdings_cache: TTLCache = TTLCache(default_ttl=86400, max_size=100, thread_safe=True)

# Fallback mapping from Yahoo Finance exchange suffixes to ISO 4217 currency codes.
# Used when ticker.price doesn't return currency data for a symbol.
EXCHANGE_CURRENCY_MAP: dict[str, str] = {
    # Asia-Pacific
    ".KS": "KRW",   # Korea (KOSPI)
    ".KQ": "KRW",   # Korea (KOSDAQ)
    ".T": "JPY",    # Tokyo
    ".HK": "HKD",   # Hong Kong
    ".SS": "CNY",   # Shanghai
    ".SZ": "CNY",   # Shenzhen
    ".TW": "TWD",   # Taiwan (TWSE)
    ".TWO": "TWD",  # Taiwan (OTC)
    ".SI": "SGD",   # Singapore
    ".AX": "AUD",   # Australia (ASX)
    ".NZ": "NZD",   # New Zealand
    ".NS": "INR",   # India (NSE)
    ".BO": "INR",   # India (BSE)
    ".JK": "IDR",   # Jakarta
    ".BK": "THB",   # Bangkok
    # Europe
    ".L": "GBP",    # London
    ".IL": "GBP",   # London (IOB)
    ".PA": "EUR",   # Paris
    ".DE": "EUR",   # XETRA (Germany)
    ".F": "EUR",    # Frankfurt
    ".MI": "EUR",   # Milan
    ".MC": "EUR",   # Madrid
    ".AS": "EUR",   # Amsterdam
    ".BR": "EUR",   # Brussels
    ".LS": "EUR",   # Lisbon
    ".HE": "EUR",   # Helsinki
    ".AT": "EUR",   # Athens
    ".VI": "EUR",   # Vienna
    ".IR": "EUR",   # Dublin
    ".OL": "NOK",   # Oslo
    ".ST": "SEK",   # Stockholm
    ".CO": "DKK",   # Copenhagen
    ".IC": "ISK",   # Iceland
    ".WA": "PLN",   # Warsaw
    ".PR": "CZK",   # Prague
    ".BD": "HUF",   # Budapest
    ".SW": "CHF",   # Swiss Exchange
    ".IS": "TRY",   # Istanbul
    # Middle East & Africa
    ".TA": "ILS",   # Tel Aviv
    ".SR": "SAR",   # Saudi (Tadawul)
    ".QA": "QAR",   # Qatar
    ".JO": "ZAR",   # Johannesburg
    # Americas
    ".TO": "CAD",   # Toronto (TSX)
    ".V": "CAD",    # TSX Venture
    ".SA": "BRL",   # Sao Paulo
    ".MX": "MXN",   # Mexico
    ".SN": "CLP",   # Santiago
    ".BA": "ARS",   # Buenos Aires
}


def currency_from_suffix(symbol: str) -> str | None:
    """Derive currency from a Yahoo Finance exchange suffix (e.g. '.KS' → 'KRW').

    Returns None if the symbol has no recognized suffix.
    """
    dot = symbol.rfind(".")
    if dot == -1:
        return None
    suffix = symbol[dot:]
    return EXCHANGE_CURRENCY_MAP.get(suffix.upper()) or EXCHANGE_CURRENCY_MAP.get(suffix)


def resolve_currency(info: dict, symbol: str) -> tuple[str, int]:
    """Resolve display currency and subunit divisor from Yahoo price info.

    Applies the standard fallback chain:
      1. Extract raw currency from the price info dict
      2. Look it up in the currency cache (handles subunits like GBp → GBP/100)
      3. Fall back to exchange-suffix mapping
      4. Default to ("USD", 1)

    Returns (display_code, divisor).
    """
    raw = info.get("currency") if isinstance(info, dict) else None
    if raw:
        return currency_lookup(raw)
    suffix_currency = currency_from_suffix(symbol)
    if suffix_currency:
        return (suffix_currency, 1)
    return ("USD", 1)


def _normalize_ohlcv_df(df: pd.DataFrame, divisor: int) -> pd.DataFrame:
    """Divide OHLCV price columns by divisor. Volume is left unchanged."""
    if divisor == 1:
        return df
    price_cols = [c for c in ("open", "high", "low", "close", "adjclose") if c in df.columns]
    df = df.copy()
    df[price_cols] = df[price_cols] / divisor
    return df


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

    # Convert subunit prices (e.g. pence → pounds)
    price_info = ticker.price.get(symbol, {})
    _, divisor = resolve_currency(price_info, symbol)
    df = _normalize_ohlcv_df(df, divisor)

    return df


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
                # Convert subunit prices (e.g. pence → pounds)
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
    This is the async version — use ``_batch_fetch_history_sync`` for
    calls from within other sync Yahoo helpers running in a thread.
    """
    return _batch_fetch_history_sync(symbols, period=period)


@async_threadable
def search(query: str, **kwargs) -> dict:
    """Search Yahoo Finance for ticker symbols."""
    return _yq_search(query, **kwargs)

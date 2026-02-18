"""Yahoo Finance data fetching via yahooquery."""

from datetime import date

import pandas as pd
from yahooquery import Ticker
from yahooquery import search as _yq_search

from app.utils import TTLCache, async_threadable

# In-memory TTL cache for ETF holdings (holdings change quarterly at most)
_holdings_cache: TTLCache = TTLCache(default_ttl=86400, max_size=100)

# Yahoo Finance uses non-standard currency codes for sub-unit currencies.
# Maps subunit codes to (main_currency_code, divisor).
SUBUNIT_CURRENCIES: dict[str, tuple[str, int]] = {
    "GBp": ("GBP", 100),
    "GBX": ("GBP", 100),
    "ILA": ("ILS", 100),
    "ZAc": ("ZAR", 100),
}


def normalize_currency(currency: str) -> tuple[str, int]:
    """Normalize a Yahoo Finance currency code.

    Returns (normalized_code, divisor). If currency is a subunit (e.g. GBp for pence),
    returns the main currency (GBP) and the divisor (100) to convert prices.
    """
    if currency in SUBUNIT_CURRENCIES:
        return SUBUNIT_CURRENCIES[currency]
    return (currency, 1)


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
    price_data = ticker.price.get(symbol, {})
    if isinstance(price_data, dict):
        raw_currency = price_data.get("currency", "USD") or "USD"
        _, divisor = normalize_currency(raw_currency)
        df = _normalize_ohlcv_df(df, divisor)

    return df


@async_threadable
def validate_symbol(symbol: str) -> dict | None:
    """Validate a ticker and return basic info, or None if invalid."""
    ticker = Ticker(symbol)
    quote = ticker.quote_type.get(symbol, {})

    if not quote or isinstance(quote, str):
        return None

    # Extract currency from price data and normalize subunits
    price_data = ticker.price.get(symbol, {})
    currency = "USD"
    if isinstance(price_data, dict):
        raw_currency = price_data.get("currency", "USD") or "USD"
        currency, _ = normalize_currency(raw_currency)

    return {
        "symbol": symbol.upper(),
        "name": quote.get("shortName") or quote.get("longName") or symbol.upper(),
        "type": quote.get("quoteType", "EQUITY"),
        "currency": currency,
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

    Returns a dict mapping symbol -> normalized currency code (e.g. "USD", "GBP").
    Subunit currencies (e.g. GBp) are normalized to their main currency.
    """
    if not symbols:
        return {}

    ticker = Ticker(symbols)
    price_data = ticker.price

    result = {}
    for sym in symbols:
        info = price_data.get(sym, {})
        if isinstance(info, dict):
            raw_currency = info.get("currency", "USD") or "USD"
            currency, _ = normalize_currency(raw_currency)
            result[sym] = currency

    return result


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

    results = []
    for sym in symbols:
        info = price_data.get(sym, {})
        if not isinstance(info, dict):
            results.append({"symbol": sym})
            continue

        raw_currency = info.get("currency", "USD") or "USD"
        currency, divisor = normalize_currency(raw_currency)

        price = info.get("regularMarketPrice")
        prev_close = info.get("regularMarketPreviousClose")
        change = info.get("regularMarketChange")
        change_pct = info.get("regularMarketChangePercent")

        results.append({
            "symbol": sym,
            "price": round(float(price) / divisor, 4) if price is not None else None,
            "previous_close": round(float(prev_close) / divisor, 4) if prev_close is not None else None,
            "change": round(float(change) / divisor, 4) if change is not None else None,
            "change_percent": round(float(change_pct) * 100, 2) if change_pct is not None else None,
            "currency": currency,
            "market_state": info.get("marketState"),
        })

    return results


def batch_fetch_history(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Fetch history for multiple symbols in one batch call.

    Subunit currencies (e.g. GBp) are converted to main units.
    """
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
                info = price_data.get(sym, {})
                if isinstance(info, dict):
                    raw_currency = info.get("currency", "USD") or "USD"
                    _, divisor = normalize_currency(raw_currency)
                    df = _normalize_ohlcv_df(df, divisor)
                result[sym] = df
        except KeyError:
            continue

    return result


@async_threadable
def search(query: str, **kwargs) -> dict:
    """Search Yahoo Finance for ticker symbols."""
    return _yq_search(query, **kwargs)

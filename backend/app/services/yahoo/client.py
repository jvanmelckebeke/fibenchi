"""Single client for all Yahoo Finance access.

Every Yahoo HTTP call in the codebase goes through :data:`yahoo_client`.
That gives us one place to apply the throttle (:mod:`rate_limit`),
quote/holdings caches, and the retry-once-with-fresh-session pattern that
keeps Yahoo's anti-bot detection from IP-blocking us.

Direct ``from yahooquery import Ticker`` imports anywhere else in the
codebase are a code smell — route the call through this client instead.

Public API (all async; sync work runs in a thread):

- :meth:`YahooClient.quotes` — real-time prices
- :meth:`YahooClient.currencies` — display currency per symbol
- :meth:`YahooClient.history` — single-symbol OHLCV
- :meth:`YahooClient.batch_history` — multi-symbol OHLCV
- :meth:`YahooClient.fundamentals` — valuation/quality metrics
- :meth:`YahooClient.validate` — symbol exists + name/type/currency
- :meth:`YahooClient.holdings` — ETF top holdings + sector weights (24h cache)
- :meth:`YahooClient.search` — Yahoo symbol search
- :meth:`YahooClient.earnings` — next earnings date + last reported date
- :meth:`YahooClient.intraday` — 1-minute bars including pre/post-market

The class is a singleton (:data:`yahoo_client`) so the throttle and
caches are shared process-wide.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import math
from datetime import date, datetime as _datetime
from typing import Any, Callable, TypeVar

import pandas as pd
from yahooquery import Ticker, search as _yq_search

from app.services.currency_service import lookup as currency_lookup
from app.services.yahoo.currency import (
    _normalize_ohlcv_df,
    currency_from_suffix,
    resolve_currency,
)
from app.services.yahoo.rate_limit import (
    CrumbRejected,
    YahooThrottle,
    check_crumb,
    yahoo_throttle as _shared_throttle,
)
from app.utils import TTLCache

logger = logging.getLogger(__name__)

# Quote response cache TTL — tuned to the SSE stream's market-hours
# interval (15s) so callers asking for the same set within the window
# share one upstream call.
QUOTE_CACHE_TTL = 12.0

# Holdings change at most quarterly, so a long TTL is safe and saves
# many Yahoo round trips.
HOLDINGS_CACHE_TTL = 86_400  # 24h

# Period strings accepted by Yahoo's history endpoint.
PERIOD_MAP: dict[str, str] = {
    "1d": "1d", "5d": "5d", "1w": "5d",
    "1mo": "1mo", "3mo": "3mo", "6mo": "6mo",
    "1y": "1y", "2y": "2y", "5y": "5y",
    "ytd": "ytd", "max": "max",
}

# Mapping: output_field → (yahoo_module, yahoo_key, decimals, multiplier)
# multiplier converts Yahoo's decimal format to percentage where needed
# (e.g. 0.15 → 15%).
FUNDAMENTAL_FIELDS: dict[str, tuple[str, str, int, float]] = {
    "forward_pe": ("key_stats", "forwardPE", 1, 1),
    "peg_ratio": ("key_stats", "pegRatio", 2, 1),
    "roe": ("financial_data", "returnOnEquity", 1, 100),
    "ev_ebitda": ("key_stats", "enterpriseToEbitda", 1, 1),
    "revenue_growth": ("financial_data", "revenueGrowth", 1, 100),
}

# Yahoo's ``sectorWeightings`` keys → human-readable sector names.
SECTOR_NAMES: dict[str, str] = {
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

_T = TypeVar("_T")


# ---------------------------------------------------------------------------
# Pure helpers — no Yahoo I/O, no client state
# ---------------------------------------------------------------------------

def _sanitize_float(val: Any) -> float | None:
    """Convert NaN/Infinity to ``None`` so ``json.dumps`` produces valid JSON."""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val


def _safe_float(val: object, multiplier: float = 1, decimals: int = 2) -> float | None:
    """Convert a Yahoo value to a safe float, or ``None`` if missing/invalid."""
    if val is None:
        return None
    try:
        f = float(val)  # type: ignore[arg-type]  # Yahoo returns mixed types
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f * multiplier, decimals)


def _normalize_date_index(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the DataFrame index contains only ``datetime.date`` objects.

    Yahoo sometimes appends an intraday row (timezone-aware ``datetime``)
    to otherwise ``date``-indexed daily data, producing a mixed-type
    object index that breaks downstream comparisons. This normalises
    every entry to a plain ``date``.
    """
    name = df.index.name
    if isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.Index(df.index.date, name=name)
    elif df.index.dtype == object and len(df) and isinstance(df.index[-1], _datetime):
        df.index = pd.Index(
            [d.date() if isinstance(d, _datetime) else d for d in df.index],
            name=name,
        )
    return df


def _parse_quote_row(sym: str, info: dict) -> dict:
    """Build one quote dict from Yahoo's per-symbol price-info dict."""
    currency, divisor = resolve_currency(info, sym)

    price = _sanitize_float(info.get("regularMarketPrice"))
    prev_close = _sanitize_float(info.get("regularMarketPreviousClose"))
    change = _sanitize_float(info.get("regularMarketChange"))
    change_pct = _sanitize_float(info.get("regularMarketChangePercent"))
    volume = info.get("regularMarketVolume")
    avg_volume = info.get("averageDailyVolume10Day")

    return {
        "symbol": sym,
        "price": round(float(price) / divisor, 4) if price is not None else None,
        "previous_close": round(float(prev_close) / divisor, 4) if prev_close is not None else None,
        "change": round(float(change) / divisor, 4) if change is not None else None,
        "change_percent": round(float(change_pct) * 100, 2) if change_pct is not None else None,
        "volume": int(volume) if volume is not None else None,
        "avg_volume": int(avg_volume) if avg_volume is not None else None,
        "currency": currency,
        "market_state": info.get("marketState"),
    }


def _parse_quotes(symbols: list[str], price_data: dict) -> list[dict]:
    """Build the full quote list, logging unusual values."""
    results: list[dict] = []
    null_symbols: list[str] = []
    nan_fields: list[str] = []

    for sym in symbols:
        info = price_data.get(sym, {})
        if not isinstance(info, dict):
            logger.warning("Yahoo returned non-dict for %s: %s", sym, repr(info)[:200])
            results.append({"symbol": sym})
            continue

        # Track NaN/null for diagnostics before sanitisation rounds them away.
        if info.get("regularMarketPrice") is not None and _sanitize_float(info["regularMarketPrice"]) is None:
            nan_fields.append(f"{sym}.price")
        if info.get("regularMarketChangePercent") is not None and _sanitize_float(info["regularMarketChangePercent"]) is None:
            nan_fields.append(f"{sym}.change_percent")
        if (info.get("regularMarketPrice") is None
                and info.get("regularMarketChangePercent") is None
                and info.get("marketState") is None):
            null_symbols.append(sym)

        results.append(_parse_quote_row(sym, info))

    if nan_fields:
        logger.warning("Yahoo returned NaN/Infinity for: %s", ", ".join(nan_fields))
    if null_symbols:
        logger.warning(
            "Yahoo returned all-null data for %d/%d symbols: %s — "
            "possible rate-limiting or auth issue",
            len(null_symbols), len(symbols), ", ".join(null_symbols[:10]),
        )

    return results


def _parse_holdings(info: dict) -> dict | None:
    """Convert Yahoo's ``fund_holding_info`` payload to our shape."""
    if not info or not isinstance(info, dict):
        return None

    holdings = []
    for h in info.get("holdings", []):
        holdings.append({
            "symbol": h.get("symbol", ""),
            "name": h.get("holdingName", ""),
            "percent": round(h.get("holdingPercent", 0) * 100, 2),
        })

    sectors = []
    for entry in info.get("sectorWeightings", []):
        for key, val in entry.items():
            pct = round(val * 100, 2)
            if pct > 0:
                sectors.append({
                    "sector": SECTOR_NAMES.get(key, key),
                    "percent": pct,
                })
    sectors.sort(key=lambda s: s["percent"], reverse=True)

    total = round(sum(h["percent"] for h in holdings), 2)

    return {
        "top_holdings": holdings,
        "sector_weightings": sectors,
        "total_percent": total,
    }


def _parse_earnings_date(raw: object) -> datetime.date | None:
    """Parse Yahoo earnings date format ("2026-04-30 16:30:S" or plain ISO)."""
    if raw is None:
        return None
    try:
        s = str(raw).strip().split(" ")[0]
        return datetime.date.fromisoformat(s)
    except (ValueError, IndexError):
        logger.debug("Could not parse earnings date: %r", raw)
        return None


def _last_reported_date(earnings_data: dict) -> datetime.date | None:
    """Extract the most recent ``reportedDate`` from ``earningsChart.quarterly``."""
    chart = earnings_data.get("earningsChart", {})
    if not isinstance(chart, dict):
        return None
    quarterly = chart.get("quarterly", [])
    if not isinstance(quarterly, list) or not quarterly:
        return None

    latest_ts = None
    for q in quarterly:
        if not isinstance(q, dict):
            continue
        ts = q.get("reportedDate")
        if ts is not None and isinstance(ts, (int, float)):
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts

    if latest_ts is None:
        return None
    try:
        return datetime.date.fromtimestamp(latest_ts)
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# YahooClient
# ---------------------------------------------------------------------------

class YahooClient:
    """Single point of access for Yahoo Finance.

    Owns the throttle, retry policy, and provider-side caches. Public
    methods are async (the sync ``yahooquery.Ticker`` calls are dispatched
    to a thread). Internal ``_*_sync`` methods are the actual fetch
    logic — useful when one operation calls another from within a thread.
    """

    def __init__(
        self,
        throttle: YahooThrottle | None = None,
        quote_cache_ttl: float = QUOTE_CACHE_TTL,
        holdings_cache_ttl: float = HOLDINGS_CACHE_TTL,
    ):
        self._throttle = throttle or _shared_throttle
        self._quote_cache: TTLCache = TTLCache(default_ttl=quote_cache_ttl, thread_safe=True)
        self._holdings_cache: TTLCache = TTLCache(
            default_ttl=holdings_cache_ttl, max_size=100, thread_safe=True,
        )

    # -- core orchestration ------------------------------------------------

    def _call(
        self,
        fetch: Callable[[], _T],
        fallback: Callable[[], _T],
        *,
        retries: int = 1,
    ) -> _T:
        """Run ``fetch`` under the throttle and circuit breaker.

        - If the breaker is tripped, returns ``fallback()`` immediately.
        - Otherwise waits for throttle clearance, then runs ``fetch``.
        - On :class:`CrumbRejected`, retries up to ``retries`` more times
          (each preceded by a fresh throttle wait) before tripping the
          breaker and returning ``fallback()``.
        - Any other exception propagates so transient errors aren't masked.
        """
        if self._throttle.is_blocked():
            return fallback()

        for attempt in range(retries + 1):
            self._throttle.wait()
            try:
                result = fetch()
            except CrumbRejected:
                if attempt < retries:
                    logger.warning(
                        "Yahoo crumb rejected — retry %d/%d with fresh session",
                        attempt + 1, retries,
                    )
                    continue
                self._throttle.record_invalid_crumb()
                return fallback()
            self._throttle.record_success()
            return result

        return fallback()  # unreachable; quiets the type checker

    # -- quotes ------------------------------------------------------------

    async def quotes(self, symbols: list[str]) -> list[dict]:
        """Fetch real-time market quotes for ``symbols``.

        Returns a list of dicts: ``symbol, price, previous_close, change,
        change_percent, volume, avg_volume, currency, market_state``. When
        the breaker is open (or Yahoo blocks), returns symbol-only
        placeholders so consumers can iterate without crashing.
        """
        return await asyncio.to_thread(self._quotes_sync, symbols)

    def _quotes_sync(self, symbols: list[str]) -> list[dict]:
        if not symbols:
            return []

        cache_key = frozenset(s.upper() for s in symbols)
        cached = self._quote_cache.get_value(cache_key)
        if cached is not None:
            return cached

        def _fetch() -> list[dict]:
            ticker = Ticker(symbols)
            data = ticker.price
            check_crumb(data)
            return _parse_quotes(symbols, data if isinstance(data, dict) else {})

        result = self._call(_fetch, fallback=lambda: [{"symbol": s} for s in symbols])
        # Don't cache the empty fallback — we want a real result on the next try.
        if any(set(r.keys()) != {"symbol"} for r in result):
            self._quote_cache.set_value(cache_key, result)
        return result

    # -- currencies --------------------------------------------------------

    async def currencies(self, symbols: list[str]) -> dict[str, str]:
        """Return display currency code per symbol (e.g. ``"USD"``, ``"GBP"``).

        Subunit currencies (e.g. ``GBp``) are normalised to the main
        currency via :func:`currency_lookup`.
        """
        return await asyncio.to_thread(self._currencies_sync, symbols)

    def _currencies_sync(self, symbols: list[str]) -> dict[str, str]:
        if not symbols:
            return {}

        def _fetch() -> dict[str, str]:
            ticker = Ticker(symbols)
            data = ticker.price
            check_crumb(data)
            out: dict[str, str] = {}
            for sym in symbols:
                raw = data.get(sym, {}) if isinstance(data, dict) else {}
                info = raw if isinstance(raw, dict) else {}
                display, _ = resolve_currency(info, sym)
                out[sym] = display
            return out

        return self._call(_fetch, fallback=lambda: {s: "USD" for s in symbols})

    # -- history -----------------------------------------------------------

    async def history(
        self,
        symbol: str,
        period: str = "3mo",
        interval: str = "1d",
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV history for a single symbol.

        Subunit currencies (e.g. ``GBp``) are converted to main units.
        Raises :class:`ValueError` when Yahoo returns no data (or the
        breaker is open and there's no fallback we can synthesise).
        """
        return await asyncio.to_thread(
            self._history_sync, symbol, period, interval, start, end,
        )

    def _history_sync(
        self,
        symbol: str,
        period: str,
        interval: str,
        start: date | None,
        end: date | None,
    ) -> pd.DataFrame:
        def _fetch() -> pd.DataFrame:
            ticker = Ticker(symbol)
            if start and end:
                df = ticker.history(start=str(start), end=str(end), interval=interval)
            else:
                normalized = PERIOD_MAP.get(period.lower(), period)
                df = ticker.history(period=normalized, interval=interval)

            if isinstance(df, dict):
                # Yahoo returns a per-symbol dict on error; check for crumb
                check_crumb(df)
                raise ValueError(f"No data found for {symbol}")
            if df.empty:
                raise ValueError(f"No data found for {symbol}")

            if isinstance(df.index, pd.MultiIndex):
                df = df.reset_index().set_index("date")

            price_info = ticker.price.get(symbol, {}) if isinstance(ticker.price, dict) else {}
            info = price_info if isinstance(price_info, dict) else {}
            _, divisor = resolve_currency(info, symbol)
            df = _normalize_ohlcv_df(df, divisor)
            return _normalize_date_index(df)

        def _fallback() -> pd.DataFrame:
            raise ValueError(f"Yahoo unavailable — cannot fetch history for {symbol}")

        return self._call(_fetch, fallback=_fallback)

    async def batch_history(
        self, symbols: list[str], period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV for many symbols in one batch.

        Subunit currencies are converted. Returns ``{}`` when the breaker
        is open or Yahoo returns no data.
        """
        return await asyncio.to_thread(self._batch_history_sync, symbols, period)

    def _batch_history_sync(
        self, symbols: list[str], period: str,
    ) -> dict[str, pd.DataFrame]:
        if not symbols:
            return {}

        def _fetch() -> dict[str, pd.DataFrame]:
            ticker = Ticker(symbols)
            price_data = ticker.price
            normalized = PERIOD_MAP.get(period.lower(), period)
            hist = ticker.history(period=normalized, interval="1d")

            if isinstance(hist, dict):
                check_crumb(hist)
                return {}
            if hist.empty:
                return {}

            out: dict[str, pd.DataFrame] = {}
            for sym in symbols:
                try:
                    if isinstance(hist.index, pd.MultiIndex):
                        df = hist.loc[sym].copy()
                    else:
                        df = hist.copy()
                    if df.empty or len(df) < 2:
                        continue
                    info = price_data.get(sym, {}) if isinstance(price_data, dict) else {}
                    info = info if isinstance(info, dict) else {}
                    _, divisor = resolve_currency(info, sym)
                    df = _normalize_ohlcv_df(df, divisor)
                    out[sym] = _normalize_date_index(df)
                except KeyError:
                    continue
            return out

        return self._call(_fetch, fallback=lambda: {})

    # -- fundamentals ------------------------------------------------------

    async def fundamentals(self, symbols: list[str]) -> dict[str, dict[str, float | None]]:
        """Fetch valuation/quality/growth fundamentals.

        Returns ``{symbol: {field: value or None}}``. Empty dicts
        (per-symbol all-None) are returned when Yahoo is unavailable.
        """
        return await asyncio.to_thread(self._fundamentals_sync, symbols)

    def _fundamentals_sync(self, symbols: list[str]) -> dict[str, dict[str, float | None]]:
        if not symbols:
            return {}

        def _fetch() -> dict[str, dict[str, float | None]]:
            ticker = Ticker(symbols)
            key_stats = ticker.key_stats
            check_crumb(key_stats)
            financial_data = ticker.financial_data
            check_crumb(financial_data)

            modules: dict[str, dict] = {
                "key_stats": key_stats if isinstance(key_stats, dict) else {},
                "financial_data": financial_data if isinstance(financial_data, dict) else {},
            }

            out: dict[str, dict[str, float | None]] = {}
            for sym in symbols:
                values: dict[str, float | None] = {}
                for output_field, (module, key, decimals, multiplier) in FUNDAMENTAL_FIELDS.items():
                    sym_data = modules[module].get(sym, {})
                    if not isinstance(sym_data, dict):
                        # Yahoo returns a string error per-symbol when data missing
                        values[output_field] = None
                        continue
                    values[output_field] = _safe_float(sym_data.get(key), multiplier, decimals)
                out[sym] = values
            return out

        def _empty() -> dict[str, dict[str, float | None]]:
            null = {f: None for f in FUNDAMENTAL_FIELDS}
            return {s: dict(null) for s in symbols}

        return self._call(_fetch, fallback=_empty)

    # -- validate ----------------------------------------------------------

    async def validate(self, symbol: str) -> dict | None:
        """Validate a ticker. Returns ``{symbol, name, type, currency,
        currency_code}`` or ``None`` if Yahoo doesn't recognise it.
        """
        return await asyncio.to_thread(self._validate_sync, symbol)

    def _validate_sync(self, symbol: str) -> dict | None:
        def _fetch() -> dict | None:
            ticker = Ticker(symbol)
            quote = ticker.quote_type.get(symbol, {})
            if not quote or isinstance(quote, str):
                return None

            price_info = ticker.price.get(symbol, {})
            raw_code: str | None = None
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

        return self._call(_fetch, fallback=lambda: None)

    # -- holdings ----------------------------------------------------------

    async def holdings(self, symbol: str) -> dict | None:
        """Fetch ETF top holdings + sector weightings (24h cache).

        Returns ``None`` for non-ETFs or when data is unavailable.
        """
        return await asyncio.to_thread(self._holdings_sync, symbol)

    def _holdings_sync(self, symbol: str) -> dict | None:
        key = symbol.upper()
        cached = self._holdings_cache.get_value(key)
        if cached is not None:
            return cached

        def _fetch() -> dict | None:
            ticker = Ticker(symbol)
            info = ticker.fund_holding_info.get(symbol)
            if isinstance(info, str):
                return None
            return _parse_holdings(info if isinstance(info, dict) else {})

        result = self._call(_fetch, fallback=lambda: None)
        self._holdings_cache.set_value(key, result)
        return result

    # -- search ------------------------------------------------------------

    async def search(self, query: str, **kwargs: Any) -> dict:
        """Search Yahoo Finance for ticker symbols. Returns Yahoo's raw payload."""
        return await asyncio.to_thread(self._search_sync, query, kwargs)

    def _search_sync(self, query: str, kwargs: dict[str, Any]) -> dict:
        def _fetch() -> dict:
            return _yq_search(query, **kwargs)

        return self._call(_fetch, fallback=lambda: {})

    # -- earnings ----------------------------------------------------------

    async def earnings(self, symbol: str) -> dict[str, object] | None:
        """Fetch next earnings date + last reported date.

        Returns ``{earnings_date, is_estimate, last_reported_date}`` or
        ``None`` when unavailable.
        """
        return await asyncio.to_thread(self._earnings_sync, symbol)

    def _earnings_sync(self, symbol: str) -> dict[str, object] | None:
        def _fetch() -> dict[str, object] | None:
            try:
                ticker = Ticker(symbol)
                cal = ticker.calendar_events
            except Exception:
                logger.exception("Failed to fetch calendar_events for %s", symbol)
                return None

            if not isinstance(cal, dict):
                return None
            check_crumb(cal)

            sym_data = cal.get(symbol)
            if not isinstance(sym_data, dict):
                return None
            earnings = sym_data.get("earnings", {})
            if not isinstance(earnings, dict):
                return None
            dates = earnings.get("earningsDate", [])
            if not isinstance(dates, list) or not dates:
                return None

            parsed = _parse_earnings_date(dates[0])
            if parsed is None:
                return None
            is_estimate = bool(earnings.get("isEarningsDateEstimate", True))

            last_reported: datetime.date | None = None
            try:
                earnings_full = ticker.earnings
                if isinstance(earnings_full, dict):
                    sym_earnings = earnings_full.get(symbol)
                    if isinstance(sym_earnings, dict):
                        last_reported = _last_reported_date(sym_earnings)
            except Exception:
                logger.debug("Could not fetch earnings history for %s", symbol)

            return {
                "earnings_date": parsed,
                "is_estimate": is_estimate,
                "last_reported_date": last_reported,
            }

        return self._call(_fetch, fallback=lambda: None)

    # -- intraday ----------------------------------------------------------

    async def intraday(self, symbols: list[str]) -> dict[str, list[dict]]:
        """Fetch 1-minute intraday bars including pre/post-market.

        Returns ``{symbol: [{timestamp, price, volume, tz_name}, ...]}``.
        Bars are divisor-normalised but NOT session-classified — that's
        the caller's job (uses exchange-hours which live in
        :mod:`app.services.intraday`).
        """
        return await asyncio.to_thread(self._intraday_sync, symbols)

    def _intraday_sync(self, symbols: list[str]) -> dict[str, list[dict]]:
        if not symbols:
            return {}

        def _fetch() -> dict[str, list[dict]]:
            ticker = Ticker(symbols)
            price_data = ticker.price

            # yahooquery's history() doesn't expose includePrePost, so call
            # the internal chart endpoint directly with the flag enabled.
            params = {"range": "1d", "interval": "1m", "includePrePost": "true"}
            data = ticker._get_data("chart", params)

            if isinstance(data, dict):
                check_crumb(data)
                for sym in symbols:
                    sym_data = data.get(sym)
                    if isinstance(sym_data, str):
                        logger.debug("Yahoo intraday error for %s: %s", sym, sym_data)

            hist = ticker._historical_data_to_dataframe(data, params, adj_timezone=True)
            if isinstance(hist, dict) or hist.empty:
                return {}

            available = (
                set(hist.index.get_level_values(0).unique())
                if isinstance(hist.index, pd.MultiIndex)
                else None
            )

            out: dict[str, list[dict]] = {}
            for sym in symbols:
                try:
                    if available is not None:
                        if sym not in available:
                            logger.debug("No intraday data returned by Yahoo for %s", sym)
                            continue
                        df = hist.loc[sym].copy()
                    else:
                        df = hist.copy()
                    if df.empty:
                        continue

                    info = price_data.get(sym, {}) if isinstance(price_data, dict) else {}
                    info = info if isinstance(info, dict) else {}
                    _, divisor = resolve_currency(info, sym)
                    tz_name = info.get("exchangeTimezoneName")

                    if not tz_name and len(df) > 0:
                        first_ts = pd.Timestamp(df.index[0])
                        if first_ts.tzinfo is not None:
                            tz_name = str(first_ts.tzinfo)

                    bars: list[dict] = []
                    for idx, row in df.iterrows():
                        ts = pd.Timestamp(idx)
                        if ts.tzinfo is None:
                            ts = ts.tz_localize("America/New_York")
                        dt = ts.to_pydatetime()

                        # Drop synthetic "current price" echo bars at
                        # non-minute-boundary timestamps. Real 1m bars
                        # land on exact minute boundaries.
                        if int(dt.timestamp()) % 60 != 0:
                            continue

                        close_val = float(row["close"])
                        if divisor != 1:
                            close_val = close_val / divisor

                        bars.append({
                            "timestamp": dt,
                            "price": round(close_val, 4),
                            "volume": int(row["volume"]) if pd.notna(row.get("volume", None)) else 0,
                            "tz_name": tz_name,
                        })
                    if bars:
                        out[sym] = bars
                except (KeyError, TypeError) as exc:
                    logger.warning("Failed to parse intraday data for %s: %s", sym, exc)
                    continue
            return out

        return self._call(_fetch, fallback=lambda: {})


# Process-wide singleton — every consumer imports this.
yahoo_client = YahooClient()


__all__ = [
    "FUNDAMENTAL_FIELDS",
    "PERIOD_MAP",
    "QUOTE_CACHE_TTL",
    "HOLDINGS_CACHE_TTL",
    "SECTOR_NAMES",
    "YahooClient",
    "yahoo_client",
    # exposed for tests that need to construct expected results
    "_parse_quote_row",
    "_parse_quotes",
    "_parse_holdings",
    "_parse_earnings_date",
    "_last_reported_date",
    "_safe_float",
    "_sanitize_float",
    "_normalize_date_index",
]

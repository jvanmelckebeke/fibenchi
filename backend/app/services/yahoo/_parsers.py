"""Pure transformations for Yahoo Finance responses.

No Yahoo I/O happens here. Functions in this module take already-fetched
Yahoo payloads and shape them into the dicts our routers serve. They're
unit-testable without mocking ``Ticker``.
"""

import datetime
import logging
import math
from datetime import datetime as _datetime
from datetime import timezone as _timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd

from app.services.yahoo.currency import resolve_currency

logger = logging.getLogger(__name__)


def _quote_session_date(info: dict) -> str | None:
    """Exchange-local calendar date of the quote's current session (ISO string).

    Derived from the /v7 quote's epoch ``regularMarketTime`` interpreted in the
    exchange's own timezone. Lets price-sync tell a still-forming current-session
    daily bar from a completed prior one when Yahoo's daily history lags the live
    session (see ``drop_unsettled_last_bar``). Best-effort: ``None`` when either
    field is absent or unparseable, in which case the sync falls back to its
    close-reconciliation heuristic.
    """
    ts = info.get("regularMarketTime")
    tz_name = info.get("exchangeTimezoneName")
    if ts is None or not tz_name:
        return None
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    try:
        # Yahoo's /v7 quote gives epoch seconds; be tolerant of a datetime too.
        if isinstance(ts, _datetime):
            moment = ts if ts.tzinfo else ts.replace(tzinfo=_timezone.utc)
        else:
            moment = _datetime.fromtimestamp(int(ts), tz=_timezone.utc)
    except (ValueError, OSError, OverflowError, TypeError):
        return None
    return moment.astimezone(tz).date().isoformat()


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


def sanitize_float(val: Any) -> float | None:
    """Convert NaN/Infinity to ``None`` so ``json.dumps`` produces valid JSON."""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val


def safe_float(val: object, multiplier: float = 1, decimals: int = 2) -> float | None:
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


def normalize_date_index(df: pd.DataFrame) -> pd.DataFrame:
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


def parse_quote_row(sym: str, info: dict) -> dict:
    """Build one quote dict from Yahoo's per-symbol price-info dict."""
    currency, divisor = resolve_currency(info, sym)

    price = sanitize_float(info.get("regularMarketPrice"))
    prev_close = sanitize_float(info.get("regularMarketPreviousClose"))
    change = sanitize_float(info.get("regularMarketChange"))
    change_pct = sanitize_float(info.get("regularMarketChangePercent"))
    volume = info.get("regularMarketVolume")
    avg_volume = info.get("averageDailyVolume10Day")

    return {
        "symbol": sym,
        "price": round(float(price) / divisor, 4) if price is not None else None,
        "previous_close": round(float(prev_close) / divisor, 4) if prev_close is not None else None,
        "change": round(float(change) / divisor, 4) if change is not None else None,
        # ``ticker.quotes`` (/v7/finance/quote) returns this already in
        # percent units (10.53 = 10.53%), unlike ``ticker.price`` which
        # returned a decimal (0.1053). No ×100 needed.
        "change_percent": round(float(change_pct), 2) if change_pct is not None else None,
        "volume": int(volume) if volume is not None else None,
        "avg_volume": int(avg_volume) if avg_volume is not None else None,
        "currency": currency,
        "market_state": info.get("marketState"),
        # Exchange-local session date (ISO str, best-effort). Internal reconciliation
        # aid for price-sync; QuoteResponse ignores it, the SSE forwards it harmlessly.
        "session_date": _quote_session_date(info),
    }


def parse_quotes(symbols: list[str], price_data: dict) -> list[dict]:
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

        if info.get("regularMarketPrice") is not None and sanitize_float(info["regularMarketPrice"]) is None:
            nan_fields.append(f"{sym}.price")
        if info.get("regularMarketChangePercent") is not None and sanitize_float(info["regularMarketChangePercent"]) is None:
            nan_fields.append(f"{sym}.change_percent")
        if (info.get("regularMarketPrice") is None
                and info.get("regularMarketChangePercent") is None
                and info.get("marketState") is None):
            null_symbols.append(sym)

        results.append(parse_quote_row(sym, info))

    if nan_fields:
        logger.warning("Yahoo returned NaN/Infinity for: %s", ", ".join(nan_fields))
    if null_symbols:
        logger.warning(
            "Yahoo returned all-null data for %d/%d symbols: %s — "
            "possible rate-limiting or auth issue",
            len(null_symbols), len(symbols), ", ".join(null_symbols[:10]),
        )

    return results


def parse_holdings(info: dict) -> dict | None:
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


def parse_earnings_date(raw: object) -> datetime.date | None:
    """Parse Yahoo earnings date format ("2026-04-30 16:30:S" or plain ISO)."""
    if raw is None:
        return None
    try:
        s = str(raw).strip().split(" ")[0]
        return datetime.date.fromisoformat(s)
    except (ValueError, IndexError):
        logger.debug("Could not parse earnings date: %r", raw)
        return None


def last_reported_date(earnings_data: dict) -> datetime.date | None:
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

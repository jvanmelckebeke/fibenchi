"""Yahoo Finance fundamental metrics fetching (valuation, quality, growth)."""

import logging
import math

from yahooquery import Ticker

from app.utils import async_threadable

logger = logging.getLogger(__name__)

# Mapping: output_field → (yahoo_module, yahoo_key, decimals, multiplier)
# multiplier converts Yahoo's decimal format to percentage where needed (e.g. 0.15 → 15%)
FUNDAMENTAL_FIELDS: dict[str, tuple[str, str, int, float]] = {
    "forward_pe": ("key_stats", "forwardPE", 1, 1),
    "peg_ratio": ("key_stats", "pegRatio", 2, 1),
    "roe": ("financial_data", "returnOnEquity", 1, 100),
    "ev_ebitda": ("key_stats", "enterpriseToEbitda", 1, 1),
    "revenue_growth": ("financial_data", "revenueGrowth", 1, 100),
}


def _safe_float(val: object, multiplier: float = 1, decimals: int = 2) -> float | None:
    """Convert a Yahoo value to a safe float, or None if missing/invalid."""
    if val is None:
        return None
    try:
        f = float(val)  # type: ignore[arg-type]  # Yahoo returns mixed types
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f * multiplier, decimals)


def _batch_fetch_fundamentals_sync(symbols: list[str]) -> dict[str, dict[str, float | None]]:
    """Fetch fundamental metrics from Yahoo Finance key_stats and financial_data.

    Returns dict[symbol, dict[field, value]] where values are already
    rounded and multiplied (e.g. ROE as percentage, not decimal).
    """
    if not symbols:
        return {}

    ticker = Ticker(symbols)

    modules: dict[str, dict] = {
        "key_stats": ticker.key_stats,
        "financial_data": ticker.financial_data,
    }

    result: dict[str, dict[str, float | None]] = {}
    for sym in symbols:
        values: dict[str, float | None] = {}
        for output_field, (module, key, decimals, multiplier) in FUNDAMENTAL_FIELDS.items():
            module_data = modules.get(module, {})
            sym_data = module_data.get(sym, {}) if isinstance(module_data, dict) else {}
            # Yahoo returns a string error message when data is unavailable
            if not isinstance(sym_data, dict):
                values[output_field] = None
                continue
            raw = sym_data.get(key)
            values[output_field] = _safe_float(raw, multiplier, decimals)
        result[sym] = values

    return result


@async_threadable
def batch_fetch_fundamentals(symbols: list[str]) -> dict[str, dict[str, float | None]]:
    """Async wrapper for batch fundamental metrics fetch."""
    return _batch_fetch_fundamentals_sync(symbols)

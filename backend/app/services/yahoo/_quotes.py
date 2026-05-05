"""Real-time quote operations on :class:`YahooClient`."""

import asyncio
import logging

from app.services.yahoo._base import _YahooBase
from app.services.yahoo._parsers import parse_quotes
from app.services.yahoo.currency import resolve_currency
from app.services.yahoo.rate_limit import check_crumb

logger = logging.getLogger(__name__)


class _QuotesMixin(_YahooBase):
    async def quotes(self, symbols: list[str]) -> list[dict]:
        """Fetch real-time market quotes for ``symbols``.

        Returns a list of dicts: ``symbol, price, previous_close, change,
        change_percent, volume, avg_volume, currency, market_state``. When
        the breaker is open or Yahoo blocks, returns symbol-only
        placeholders so consumers can iterate without crashing.
        """
        if not symbols:
            return []

        cache_key = frozenset(s.upper() for s in symbols)
        cached = self._quote_cache.get_value(cache_key)
        if cached is not None:
            return cached

        def _fetch() -> list[dict]:
            ticker = self._ticker(symbols)
            # ``quotes`` hits the batched ``/v7/finance/quote?symbols=…``
            # endpoint (one HTTP call for all symbols), unlike ``price``
            # which fans out via per-symbol quoteSummary requests.
            data = ticker.quotes
            check_crumb(data)
            return parse_quotes(symbols, data if isinstance(data, dict) else {})

        result = await asyncio.to_thread(
            self._call, _fetch, lambda: [{"symbol": s} for s in symbols],
        )
        # Don't cache the empty fallback — we want a real result on the next try.
        if any(set(r.keys()) != {"symbol"} for r in result):
            self._quote_cache.set_value(cache_key, result)
        return result

    async def currencies(self, symbols: list[str]) -> dict[str, str]:
        """Return display currency code per symbol (e.g. ``"USD"``, ``"GBP"``).

        Subunit currencies (e.g. ``GBp``) are normalised via the lookup
        table.
        """
        if not symbols:
            return {}

        def _fetch() -> dict[str, str]:
            ticker = self._ticker(symbols)
            data = ticker.quotes
            check_crumb(data)
            out: dict[str, str] = {}
            for sym in symbols:
                raw = data.get(sym, {}) if isinstance(data, dict) else {}
                info = raw if isinstance(raw, dict) else {}
                display, _ = resolve_currency(info, sym)
                out[sym] = display
            return out

        return await asyncio.to_thread(
            self._call, _fetch, lambda: {s: "USD" for s in symbols},
        )

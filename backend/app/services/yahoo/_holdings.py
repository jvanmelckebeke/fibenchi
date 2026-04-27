"""ETF holdings operations on :class:`YahooClient`."""

import asyncio

from app.services.yahoo._base import _YahooBase
from app.services.yahoo._parsers import parse_holdings


class _HoldingsMixin(_YahooBase):
    async def holdings(self, symbol: str) -> dict | None:
        """Fetch ETF top holdings + sector weightings (24h cache).

        Returns ``None`` for non-ETFs or when data is unavailable.
        """
        key = symbol.upper()
        cached = self._holdings_cache.get_value(key)
        if cached is not None:
            return cached

        def _fetch() -> dict | None:
            ticker = self._ticker(symbol)
            info = ticker.fund_holding_info.get(symbol)
            if isinstance(info, str):
                return None
            return parse_holdings(info if isinstance(info, dict) else {})

        result = await asyncio.to_thread(self._call, _fetch, lambda: None)
        self._holdings_cache.set_value(key, result)
        return result

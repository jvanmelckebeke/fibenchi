"""Symbol validation operations on :class:`YahooClient`."""

import asyncio

from app.services.currency_service import lookup as currency_lookup
from app.services.yahoo._base import _YahooBase
from app.services.yahoo.currency import currency_from_suffix


class _ValidationMixin(_YahooBase):
    async def validate(self, symbol: str) -> dict | None:
        """Validate a ticker. Returns ``{symbol, name, type, currency,
        currency_code}`` or ``None`` if Yahoo doesn't recognise it.
        """
        def _fetch() -> dict | None:
            ticker = self._ticker(symbol)
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

        return await asyncio.to_thread(self._call, _fetch, lambda: None)

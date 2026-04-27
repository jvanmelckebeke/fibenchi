"""Fundamental metrics (valuation/quality/growth) on :class:`YahooClient`."""

import asyncio

from app.services.yahoo._base import _YahooBase
from app.services.yahoo._parsers import FUNDAMENTAL_FIELDS, safe_float
from app.services.yahoo.rate_limit import check_crumb


class _FundamentalsMixin(_YahooBase):
    async def fundamentals(self, symbols: list[str]) -> dict[str, dict[str, float | None]]:
        """Fetch valuation/quality/growth fundamentals.

        Returns ``{symbol: {field: value or None}}``. All-None dicts
        are returned when Yahoo is unavailable.
        """
        if not symbols:
            return {}

        def _fetch() -> dict[str, dict[str, float | None]]:
            ticker = self._ticker(symbols)
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
                    values[output_field] = safe_float(sym_data.get(key), multiplier, decimals)
                out[sym] = values
            return out

        def _empty() -> dict[str, dict[str, float | None]]:
            null = {f: None for f in FUNDAMENTAL_FIELDS}
            return {s: dict(null) for s in symbols}

        return await asyncio.to_thread(self._call, _fetch, _empty)

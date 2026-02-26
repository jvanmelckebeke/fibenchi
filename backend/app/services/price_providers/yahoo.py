"""Yahoo Finance price provider — thin wrapper around existing yahoo/ functions."""

import asyncio
from datetime import date

import pandas as pd

from app.services.price_providers.base import PriceProvider
from app.services.yahoo import (
    batch_fetch_history as _batch_fetch_history,
    batch_fetch_quotes as _batch_fetch_quotes,
    fetch_history as _fetch_history,
)
from app.services.yahoo.quotes import batch_fetch_currencies as _batch_fetch_currencies_sync


class YahooPriceProvider(PriceProvider):
    """Delegates all price operations to the existing yahoo/ service package."""

    async def fetch_history(
        self,
        symbol: str,
        period: str = "3mo",
        interval: str = "1d",
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        return await _fetch_history(
            symbol, period=period, interval=interval, start=start, end=end,
        )

    async def batch_fetch_history(
        self, symbols: list[str], period: str = "1y"
    ) -> dict[str, pd.DataFrame]:
        return await _batch_fetch_history(symbols, period=period)

    async def batch_fetch_quotes(self, symbols: list[str]) -> list[dict]:
        return await _batch_fetch_quotes(symbols)

    async def batch_fetch_currencies(self, symbols: list[str]) -> dict[str, str]:
        return await asyncio.to_thread(_batch_fetch_currencies_sync, symbols)

"""Yahoo Finance price provider — facade over :data:`yahoo_client`.

The throttle, circuit breaker, and per-endpoint caches all live in
:class:`~app.services.yahoo.client.YahooClient`. This class only exists
so the abstract :class:`PriceProvider` interface stays decoupled from
Yahoo specifics — a future provider (Finnhub, Polygon) implements
``PriceProvider`` directly without inheriting Yahoo's resilience quirks.
"""

from datetime import date

import pandas as pd

from app.services.price_providers.base import PriceProvider
from app.services.yahoo import yahoo_client


class YahooPriceProvider(PriceProvider):
    """Thin facade — every method delegates to ``yahoo_client``."""

    async def fetch_history(
        self,
        symbol: str,
        period: str = "3mo",
        interval: str = "1d",
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        return await yahoo_client.history(
            symbol, period=period, interval=interval, start=start, end=end,
        )

    async def batch_fetch_history(
        self, symbols: list[str], period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        return await yahoo_client.batch_history(symbols, period=period)

    async def batch_fetch_quotes(self, symbols: list[str]) -> list[dict]:
        return await yahoo_client.quotes(symbols)

    async def batch_fetch_currencies(self, symbols: list[str]) -> dict[str, str]:
        return await yahoo_client.currencies(symbols)

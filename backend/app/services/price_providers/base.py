"""Abstract base class for price data providers."""

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class PriceProvider(ABC):
    """Provider interface for OHLCV price data, quotes, and currency info.

    Implementations wrap a specific data source (Yahoo Finance, IBKR, etc.).
    Consumers call get_price_provider() and use this interface without
    knowing which backend is active.
    """

    @abstractmethod
    async def fetch_history(
        self,
        symbol: str,
        period: str = "3mo",
        interval: str = "1d",
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV history for a single symbol.

        Returns DataFrame with index=date, columns=[open, high, low, close, volume].
        Raises ValueError if no data is available.
        """

    @abstractmethod
    async def batch_fetch_history(
        self, symbols: list[str], period: str = "1y"
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV history for multiple symbols in one call.

        Returns {symbol: DataFrame} for symbols that have data.
        """

    @abstractmethod
    async def batch_fetch_quotes(self, symbols: list[str]) -> list[dict]:
        """Fetch current market quotes for multiple symbols.

        Returns list of dicts with keys: symbol, price, previous_close,
        change, change_percent, volume, avg_volume, currency, market_state.
        """

    @abstractmethod
    async def batch_fetch_currencies(self, symbols: list[str]) -> dict[str, str]:
        """Fetch display currency codes for multiple symbols.

        Returns {symbol: currency_code} (e.g. {"AAPL": "USD", "ABI.BR": "EUR"}).
        """

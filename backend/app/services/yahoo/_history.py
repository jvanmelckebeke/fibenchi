"""OHLCV history operations on :class:`YahooClient`."""

import asyncio
import logging
from datetime import date

import pandas as pd

from app.services.yahoo._base import _YahooBase
from app.services.yahoo._parsers import PERIOD_MAP, normalize_date_index
from app.services.yahoo.currency import _normalize_ohlcv_df, resolve_currency
from app.services.yahoo.rate_limit import check_crumb

logger = logging.getLogger(__name__)


class _HistoryMixin(_YahooBase):
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
        Raises :class:`ValueError` when Yahoo returns no data or the
        breaker is open.
        """
        def _fetch() -> pd.DataFrame:
            ticker = self._ticker(symbol)
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
            return normalize_date_index(df)

        def _fallback() -> pd.DataFrame:
            raise ValueError(f"Yahoo unavailable — cannot fetch history for {symbol}")

        return await asyncio.to_thread(self._call, _fetch, _fallback)

    async def batch_history(
        self, symbols: list[str], period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV for many symbols in one batch.

        Subunit currencies are converted. Returns ``{}`` when the breaker
        is open or Yahoo returns no data.
        """
        if not symbols:
            return {}

        def _fetch() -> dict[str, pd.DataFrame]:
            ticker = self._ticker(symbols)
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
                    out[sym] = normalize_date_index(df)
                except KeyError:
                    continue
            return out

        return await asyncio.to_thread(self._call, _fetch, lambda: {})

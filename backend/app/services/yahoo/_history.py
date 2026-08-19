"""OHLCV history operations on :class:`YahooClient`."""

import asyncio
import logging
from datetime import date

import pandas as pd

from app.services.compute.splits import normalize_splits
from app.services.yahoo._base import _YahooBase
from app.services.yahoo._parsers import PERIOD_MAP, normalize_date_index
from app.services.yahoo.currency import _normalize_ohlcv_df, resolve_currency
from app.services.yahoo.rate_limit import check_crumb

logger = logging.getLogger(__name__)


def padded_history_frame(ticker, data, params: dict, symbols: list[str]) -> pd.DataFrame:
    """``Ticker._historical_data_to_dataframe`` minus the KeyError (#593).

    yahooquery indexes ``data[symbol]`` for every requested symbol, so a
    symbol Yahoo omitted *entirely* from the chart response — distinct from
    the handled case of an error payload under the symbol's key — raises
    KeyError and takes the whole batch down with it (staging 2026-08-05: an
    omitted 2914.T aborted a full 82-symbol intraday sync; an omitted
    IWDA.AS 500'd holdings-indicators). Padding the omitted symbols with an
    empty payload makes yahooquery filter them like any other no-data
    symbol, degrading one omission to one missing symbol.
    """
    if isinstance(data, dict):
        missing = [s for s in symbols if s not in data]
        if missing:
            logger.warning(
                "Yahoo chart response omitted %d/%d symbol(s): %s",
                len(missing), len(symbols), ", ".join(sorted(missing)),
            )
            data = {**data, **{s: {} for s in missing}}
    return ticker._historical_data_to_dataframe(data, params, True)


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

        Subunit currencies (e.g. ``GBp``) are converted to main units, and
        pre-split bars are rebased onto the current share basis, so the frame
        is continuous in one unit end to end (#648).

        Raises :class:`ValueError` when Yahoo returns no data or the
        breaker is open.
        """
        def _fetch() -> pd.DataFrame:
            ticker = self._ticker(symbol)
            try:
                if start and end:
                    df = ticker.history(start=str(start), end=str(end), interval=interval)
                else:
                    normalized = PERIOD_MAP.get(period.lower(), period)
                    df = ticker.history(period=normalized, interval=interval)
            except KeyError:
                # Yahoo omitted the (only) symbol from its own chart response
                # (#593) — for a single-symbol fetch that simply is "no data".
                raise ValueError(f"No data found for {symbol}") from None

            if isinstance(df, dict):
                # Yahoo returns a per-symbol dict on error; check for crumb
                check_crumb(df)
                raise ValueError(f"No data found for {symbol}")
            if df.empty:
                raise ValueError(f"No data found for {symbol}")

            if isinstance(df.index, pd.MultiIndex):
                df = df.reset_index().set_index("date")

            quote_data = ticker.quotes
            price_info = quote_data.get(symbol, {}) if isinstance(quote_data, dict) else {}
            info = price_info if isinstance(price_info, dict) else {}
            _, divisor = resolve_currency(info, symbol)
            df = _normalize_ohlcv_df(df, divisor)
            df = normalize_splits(df, symbol)
            return normalize_date_index(df)

        def _fallback() -> pd.DataFrame:
            raise ValueError(f"Yahoo unavailable — cannot fetch history for {symbol}")

        return await asyncio.to_thread(self._call, _fetch, _fallback)

    async def batch_history(
        self, symbols: list[str], period: str = "1y",
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV for many symbols in one batch.

        Subunit currencies are converted and splits rebased, as in
        :meth:`history`. Returns ``{}`` when the breaker is open or Yahoo
        returns no data.
        """
        if not symbols:
            return {}

        def _fetch() -> dict[str, pd.DataFrame]:
            ticker = self._ticker(symbols)
            # ``quotes`` is one batched HTTP call regardless of N, vs.
            # ``price`` which fans out per symbol via quoteSummary.
            price_data = ticker.quotes
            normalized = PERIOD_MAP.get(period.lower(), period)
            # The chart endpoint is called directly (what ``ticker.history``
            # does internally for a period fetch) so the raw response can be
            # padded before frame-building — one symbol Yahoo omitted must
            # degrade to that symbol missing, not a KeyError that costs the
            # whole batch (#593).
            params = {"range": normalized.lower(), "interval": "1d"}
            data = ticker._get_data("chart", params)
            check_crumb(data)
            hist = padded_history_frame(ticker, data, params, symbols)

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
                        logger.debug("batch_history: %s returned %d rows; skipping", sym, len(df))
                        continue
                    info = price_data.get(sym, {}) if isinstance(price_data, dict) else {}
                    info = info if isinstance(info, dict) else {}
                    _, divisor = resolve_currency(info, sym)
                    df = _normalize_ohlcv_df(df, divisor)
                    df = normalize_splits(df, sym)
                    out[sym] = normalize_date_index(df)
                except KeyError:
                    logger.debug("batch_history: %s missing from Yahoo batch response", sym)
                    continue
            return out

        return await asyncio.to_thread(self._call, _fetch, lambda: {})

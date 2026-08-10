"""1-minute intraday bars on :class:`YahooClient`."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from app.services.yahoo._base import _YahooBase
from app.services.yahoo._history import padded_history_frame
from app.services.yahoo.currency import resolve_currency
from app.services.yahoo.rate_limit import check_crumb

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderIntradayBar:
    """One raw 1-minute bar as fetched from Yahoo.

    Provider-internal transport shape: divisor-normalised but not yet
    session-classified — :mod:`app.services.intraday` classifies (using
    ``tz_name`` as a venue-less fallback) and persists, at which point the
    bar becomes an :class:`~app.models.intraday.IntradayPrice` row.
    """

    timestamp: datetime  # tz-aware
    price: float
    volume: int
    tz_name: str | None


class _IntradayMixin(_YahooBase):
    async def intraday(self, symbols: list[str]) -> dict[str, list[ProviderIntradayBar]]:
        """Fetch 1-minute intraday bars including pre/post-market.

        Returns ``{symbol: [ProviderIntradayBar, ...]}``. Bars are
        divisor-normalised but NOT session-classified — that's the caller's
        job (uses exchange-hours which live in :mod:`app.services.intraday`).
        """
        if not symbols:
            return {}

        def _fetch() -> dict[str, list[ProviderIntradayBar]]:
            ticker = self._ticker(symbols)
            price_data = ticker.price

            # yahooquery's history() doesn't expose includePrePost, so call
            # the internal chart endpoint directly with the flag enabled.
            params = {"range": "1d", "interval": "1m", "includePrePost": "true"}
            data = ticker._get_data("chart", params)

            if isinstance(data, dict):
                check_crumb(data)
                for sym in symbols:
                    sym_data = data.get(sym)
                    if isinstance(sym_data, str):
                        logger.debug("Yahoo intraday error for %s: %s", sym, sym_data)

            hist = padded_history_frame(ticker, data, params, symbols)
            if hist.empty:
                return {}

            available = (
                set(hist.index.get_level_values(0).unique())
                if isinstance(hist.index, pd.MultiIndex)
                else None
            )

            out: dict[str, list[ProviderIntradayBar]] = {}
            for sym in symbols:
                try:
                    if available is not None:
                        if sym not in available:
                            logger.debug("No intraday data returned by Yahoo for %s", sym)
                            continue
                        df = hist.loc[sym].copy()
                    else:
                        df = hist.copy()
                    if df.empty:
                        continue

                    info = price_data.get(sym, {}) if isinstance(price_data, dict) else {}
                    info = info if isinstance(info, dict) else {}
                    _, divisor = resolve_currency(info, sym)
                    tz_name = info.get("exchangeTimezoneName")

                    if not tz_name and len(df) > 0:
                        first_ts = pd.Timestamp(df.index[0])
                        if first_ts.tzinfo is not None:
                            tz_name = str(first_ts.tzinfo)

                    bars: list[ProviderIntradayBar] = []
                    for idx, row in df.iterrows():
                        ts = pd.Timestamp(idx)
                        if ts.tzinfo is None:
                            ts = ts.tz_localize("America/New_York")
                        dt = ts.to_pydatetime()

                        # Drop synthetic "current price" echo bars at
                        # non-minute-boundary timestamps. Real 1m bars
                        # land on exact minute boundaries.
                        if int(dt.timestamp()) % 60 != 0:
                            continue

                        close_val = float(row["close"])
                        if divisor != 1:
                            close_val = close_val / divisor

                        bars.append(ProviderIntradayBar(
                            timestamp=dt,
                            price=round(close_val, 4),
                            volume=int(row["volume"]) if pd.notna(row.get("volume", None)) else 0,
                            tz_name=tz_name,
                        ))
                    if bars:
                        out[sym] = bars
                except (KeyError, TypeError) as exc:
                    logger.warning("Failed to parse intraday data for %s: %s", sym, exc)
                    continue
            return out

        return await asyncio.to_thread(self._call, _fetch, lambda: {})

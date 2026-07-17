"""Sync price data from the configured price provider to the database."""

import logging
from datetime import date

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset
from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.services.price_providers import PriceProvider, get_price_provider

logger = logging.getLogger(__name__)

# The frontend's σ-Move (vnr) only trusts a stored daily bar when its close
# reconciles with the live quote — within this tolerance of either the current
# price (same session) or the previous close (prior session). Keep it in sync
# with ``SESSION_MATCH_TOL`` in ``frontend/src/lib/indicator-registry.ts``.
SESSION_MATCH_TOL = 0.005  # 0.5%

# Market states in which the current session's daily bar is still forming, so
# the trailing bar Yahoo returns is a live partial regardless of whether it
# momentarily matches the live price. Other states (PRE/PREPRE before the open,
# POST/POSTPOST/CLOSED after it) leave a settled daily bar we reconcile instead.
_ACTIVE_SESSION_STATES = frozenset({"REGULAR"})


def _reconciles(a: float | None, b: float | None, tol: float = SESSION_MATCH_TOL) -> bool:
    """True when ``a`` is within ``tol`` (relative) of ``b``."""
    if a is None or b is None or b == 0:
        return False
    return abs(a - b) / abs(b) <= tol


def drop_unsettled_last_bar(
    df: pd.DataFrame,
    price: float | None,
    previous_close: float | None,
    market_state: str | None,
    symbol: str | None = None,
) -> pd.DataFrame:
    """Drop a trailing daily bar that reflects an in-progress / unsettled session.

    Yahoo's daily history appends a live, still-forming bar for the current
    session, and a sync running mid-session (or before Yahoo settles the bar
    after a market's close) persists that partial value. Once the price moves
    on, the stored close matches neither the live price nor the previous close,
    so the frontend blanks σ-Move (see ``isStoredVnrStale``).

    This keeps the daily table to *completed* sessions. The last bar is dropped
    when it is identifiably the current session (its predecessor equals the
    quote's previous close) AND it is not yet final — either because the market
    is still open (``market_state`` active; the partial matches the live price
    now but will drift) or because the market has closed but Yahoo's daily bar
    has not settled to the live close. The remaining most-recent bar is then the
    last completed close, which always reconciles, letting the frontend
    recompute σ-Move live from the quote.

    A no-op (returns ``df`` unchanged) when the quote is missing, the frame is
    too short to have a predecessor, the last bar is already a completed prior
    session, or a closed session's bar has settled to the live price.
    """
    if len(df) < 2 or price is None or previous_close is None:
        return df

    last_close = float(df.iloc[-1]["close"])
    prev_bar_close = float(df.iloc[-2]["close"])

    # Only act when the trailing bar is the current session (its predecessor is
    # the quote's previous close). Otherwise it is already a completed bar.
    if not _reconciles(prev_bar_close, previous_close):
        return df

    # An open session's bar is always a live partial — drop it even though it
    # matches the live price right now, because it will drift as trading goes on.
    if market_state in _ACTIVE_SESSION_STATES:
        logger.debug(
            "%s: dropping trailing %s bar (session open; close=%s, live=%s)",
            symbol or "?", df.index[-1], last_close, price,
        )
        return df.iloc[:-1]

    # Market closed: keep the bar once it has settled to the live close; drop it
    # while Yahoo's daily feed still lags the (already-settled) quote.
    if _reconciles(last_close, price):
        return df

    # Noteworthy: this leaves the symbol without its latest session's bar. Once
    # the quote's previous_close rolls at the next open, the remaining stored
    # bar reconciles with nothing and σ-Move blanks until a sync stores it.
    logger.info(
        "%s: dropping trailing %s bar (market %s; close=%s hasn't settled to quote %s)",
        symbol or "?", df.index[-1], market_state, last_close, price,
    )
    return df.iloc[:-1]


async def _quote_anchors(
    provider: PriceProvider, symbols: list[str],
) -> dict[str, tuple[float | None, float | None, str | None]]:
    """Fetch ``{symbol: (price, previous_close, market_state)}`` for reconciliation.

    Best-effort: a quote-fetch failure degrades to storing every bar (the prior
    behaviour) rather than aborting the sync.
    """
    if not symbols:
        return {}
    try:
        quotes = await provider.batch_fetch_quotes(symbols)
    except Exception:
        logger.warning("Quote fetch for settlement check failed; storing all bars", exc_info=True)
        return {}
    return {
        q["symbol"]: (q.get("price"), q.get("previous_close"), q.get("market_state"))
        for q in quotes
        if q.get("symbol")
    }


async def sync_asset_prices(db: AsyncSession, asset: Asset, period: str = "3mo") -> int:
    """Fetch and upsert price data for a single asset. Returns number of rows upserted."""
    provider = get_price_provider()
    df = await provider.fetch_history(asset.symbol, period=period)
    price, previous_close, market_state = (await _quote_anchors(provider, [asset.symbol])).get(
        asset.symbol, (None, None, None)
    )
    df = drop_unsettled_last_bar(df, price, previous_close, market_state, symbol=asset.symbol)
    return await _upsert_prices(db, asset.id, df)


async def sync_asset_prices_range(
    db: AsyncSession, asset: Asset, start: date, end: date
) -> int:
    """Fetch and upsert price data for a date range. Returns number of rows upserted."""
    provider = get_price_provider()
    df = await provider.fetch_history(asset.symbol, start=start, end=end)
    return await _upsert_prices(db, asset.id, df)


async def sync_all_prices(db: AsyncSession, period: str = "1y") -> dict[str, int]:
    """Fetch and upsert prices for all tracked assets. Returns {symbol: count}."""
    assets = await AssetRepository(db).list_all()

    if not assets:
        return {}

    symbols = [a.symbol for a in assets]
    asset_map = {a.symbol: a.id for a in assets}
    provider = get_price_provider()
    data = await provider.batch_fetch_history(symbols, period=period)
    anchors = await _quote_anchors(provider, symbols)

    counts = {}
    for sym, df in data.items():
        asset_id = asset_map.get(sym)
        if asset_id:
            price, previous_close, market_state = anchors.get(sym, (None, None, None))
            df = drop_unsettled_last_bar(df, price, previous_close, market_state, symbol=sym)
            counts[sym] = await _upsert_prices(db, asset_id, df)

    # The batch response silently omits symbols Yahoo hiccupped on; without a
    # retry those stay stale until the next scheduled run (up to a full day).
    missing = [s for s in symbols if s not in data]
    if missing and not data:
        logger.error(
            "Batch history returned no data for all %d symbols; skipping per-symbol retries",
            len(symbols),
        )
    elif missing:
        logger.warning(
            "Batch history missing %d/%d symbols; retrying individually: %s",
            len(missing), len(symbols), ", ".join(sorted(missing)),
        )
        for sym in missing:
            try:
                df = await provider.fetch_history(sym, period=period)
            except Exception:
                logger.warning("Retry fetch for %s failed", sym, exc_info=True)
                continue
            if df is None or df.empty:
                logger.warning("Retry fetch for %s returned no data", sym)
                continue
            price, previous_close, market_state = anchors.get(sym, (None, None, None))
            df = drop_unsettled_last_bar(df, price, previous_close, market_state, symbol=sym)
            counts[sym] = await _upsert_prices(db, asset_map[sym], df)

    return counts


async def _upsert_prices(db: AsyncSession, asset_id: int, df: pd.DataFrame) -> int:
    """Upsert price rows from a DataFrame. Returns row count."""
    return await PriceRepository(db).upsert_prices(asset_id, df)

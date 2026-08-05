"""Sync price data from the configured price provider to the database."""

import logging
from datetime import date

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset
from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.services.market_state import is_session_forming
from app.services.price_providers import PriceProvider, get_price_provider

logger = logging.getLogger(__name__)

# The frontend's σ-Move (vnr) only trusts a stored daily bar when its close
# reconciles with the live quote — within this tolerance of either the current
# price (same session) or the previous close (prior session). Keep it in sync
# with ``SESSION_MATCH_TOL`` in ``frontend/src/lib/indicator-registry.ts``.
SESSION_MATCH_TOL = 0.005  # 0.5%

# "Is the current session's daily bar still forming?" now comes from the
# shared market-state trait table (is_session_forming): in REGULAR the trailing
# bar Yahoo returns is a live partial regardless of whether it momentarily
# matches the live price; every other state (PRE/PREPRE before the open,
# POST/POSTPOST/CLOSED after it) leaves a settled daily bar we reconcile.


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
    session_date: date | None = None,
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

    ``session_date`` is the current session's exchange-local date (from the
    quote). When known, it disambiguates the one case the close heuristic can't:
    if Yahoo's daily feed hasn't appended today's forming bar yet, the trailing
    row is a *completed* prior session whose own predecessor can still fall
    within tol of ``previous_close`` (a flat prior day) — which would otherwise
    misfire the drop and discard a real completed bar. A trailing bar dated
    before the session is therefore kept.

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

    # If we know the live session's date and the trailing bar predates it, Yahoo
    # simply hasn't appended today's forming bar yet: this row is a completed
    # prior session, not an unsettled one — keep it. (Without this a flat prior
    # day, where the predecessor also matches ``previous_close``, would be
    # wrongly dropped and blank σ-Move until a heal.)
    if session_date is not None:
        last_bar_dt = df.index[-1]
        last_bar_date = last_bar_dt.date() if hasattr(last_bar_dt, "date") else last_bar_dt
        if last_bar_date < session_date:
            return df

    # An open session's bar is always a live partial — drop it even though it
    # matches the live price right now, because it will drift as trading goes on.
    if is_session_forming(market_state):
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


# A per-symbol reconciliation anchor: (price, previous_close, market_state,
# session_date). ``session_date`` is the exchange-local date of the live
# session, used to keep a completed bar Yahoo's feed hasn't superseded yet.
Anchor = tuple[float | None, float | None, str | None, date | None]
_NO_ANCHOR: Anchor = (None, None, None, None)


def _as_date(value: str | None) -> date | None:
    """Parse an ISO date string (from a quote's ``session_date``) to a date."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


async def _quote_anchors(
    provider: PriceProvider, symbols: list[str],
) -> dict[str, Anchor]:
    """Fetch ``{symbol: (price, previous_close, market_state, session_date)}``.

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
        q["symbol"]: (
            q.get("price"), q.get("previous_close"),
            q.get("market_state"), _as_date(q.get("session_date")),
        )
        for q in quotes
        if q.get("symbol")
    }


async def _drop_and_persist(
    db: AsyncSession, asset_id: int, df: pd.DataFrame, anchor: Anchor, symbol: str,
) -> int:
    """Drop the trailing unsettled bar (if any), upsert the rest, and purge any
    stale copy left behind. Returns the number of rows upserted.

    When the trailing bar is dropped, a partial persisted at that date by an
    earlier (e.g. quote-degraded) sync would linger in the DB — upsert only
    touches the completed rows it received, so it can never clear a row it no
    longer has. That orphan keeps ``get_latest_closes`` returning an unreconciled
    close and blanks σ-Move for the whole session. Delete any row past the last
    kept bar so the settled data is authoritative.
    """
    price, previous_close, market_state, session_date = anchor
    kept = drop_unsettled_last_bar(
        df, price, previous_close, market_state, symbol=symbol, session_date=session_date,
    )
    count = await _upsert_prices(db, asset_id, kept)
    if not kept.empty and len(kept) < len(df):
        last_kept = kept.index[-1]
        last_kept = last_kept.date() if hasattr(last_kept, "date") else last_kept
        await PriceRepository(db).delete_prices_after(asset_id, last_kept)
    return count


async def _persist_symbol(
    db: AsyncSession, asset_id: int, df: pd.DataFrame, anchor: Anchor, symbol: str,
) -> int | None:
    """Persist one symbol's frame, isolating its failure from the rest of the run.

    ``sync_all_prices`` shares one session across every symbol, and each symbol
    commits independently (``_drop_and_persist`` upserts then purges, both of
    which commit). Without this guard a single symbol raising — a malformed frame
    or a mid-transaction DB error — aborts the whole nightly refresh, leaving
    every symbol after it stale until the next run. On failure we roll back so a
    half-applied transaction can't poison the session for the following symbols
    (only the failed symbol's uncommitted work is discarded; prior symbols have
    already committed) and return ``None`` to skip it.
    """
    try:
        return await _drop_and_persist(db, asset_id, df, anchor, symbol)
    except Exception:
        logger.warning("Persisting prices for %s failed; skipping", symbol, exc_info=True)
        await db.rollback()
        return None


async def sync_asset_prices(
    db: AsyncSession, asset: Asset, period: str = "3mo", anchor: Anchor | None = None,
) -> int:
    """Fetch and upsert price data for a single asset. Returns number of rows upserted.

    ``anchor`` lets a caller that already holds the symbol's reconciliation
    anchor (e.g. the price-heal loop, which batch-fetched every quote) pass it
    in, avoiding a redundant per-symbol quote round-trip.
    """
    provider = get_price_provider()
    df = await provider.fetch_history(asset.symbol, period=period)
    if anchor is None:
        anchor = (await _quote_anchors(provider, [asset.symbol])).get(asset.symbol, _NO_ANCHOR)
    return await _drop_and_persist(db, asset.id, df, anchor, asset.symbol)


async def sync_asset_prices_range(
    db: AsyncSession, asset: Asset, start: date, end: date
) -> int:
    """Fetch and upsert price data for a date range. Returns number of rows upserted.

    A range that reaches today can include the current session's still-forming
    bar, exactly like a period fetch — this path used to upsert it raw, so any
    display/warmup backfill during market hours stored a live partial that
    drifted from the quote and blanked σ-Move for the rest of the session.
    Routing through the same anchor + drop + purge as ``sync_asset_prices``
    closes that hole. Purely historical ranges (interior hole heals, bounded
    backfills) skip the quote round-trip: every bar in them is settled.
    """
    provider = get_price_provider()
    df = await provider.fetch_history(asset.symbol, start=start, end=end)
    if end < date.today():
        return await _upsert_prices(db, asset.id, df)
    anchor = (await _quote_anchors(provider, [asset.symbol])).get(asset.symbol, _NO_ANCHOR)
    return await _drop_and_persist(db, asset.id, df, anchor, asset.symbol)


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
            count = await _persist_symbol(db, asset_id, df, anchors.get(sym, _NO_ANCHOR), sym)
            if count is not None:
                counts[sym] = count

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
            count = await _persist_symbol(db, asset_map[sym], df, anchors.get(sym, _NO_ANCHOR), sym)
            if count is not None:
                counts[sym] = count

    return counts


async def _upsert_prices(db: AsyncSession, asset_id: int, df: pd.DataFrame) -> int:
    """Upsert price rows from a DataFrame. Returns row count."""
    return await PriceRepository(db).upsert_prices(asset_id, df)

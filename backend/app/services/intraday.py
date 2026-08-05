"""Intraday price fetching, storage, and cleanup for live day view."""

import logging
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intraday import IntradayPrice
from app.services.market_calendar import Symbol
from app.services.yahoo import yahoo_client

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

# Venue phase → the 3-value session vocabulary the intraday chart stores/reads.
_PHASE_TO_SESSION = {"premarket": "pre", "open": "regular", "aftermarket": "post"}


def _classify_session(ts: datetime, symbol: str, tz_name: str | None = None) -> str:
    """Classify a bar timestamp as pre/regular/post.

    Venue-schedule based (``Symbol(symbol).venue.phase``): holiday- and
    half-day-aware — the old hand-maintained wall-clock table filed bars
    after a 13:00 ET early close as "regular". Venues without extended hours
    can still print auction/late bars outside regular sessions; those
    "closed" instants are filed to the nearer session boundary (evening →
    post, next morning → pre) to preserve the 3-value storage.

    Fallback when no venue resolves: wall-clock against the bar's own
    exchange timezone with generic 09:00–17:30 hours, or US Eastern regular
    hours when even the timezone is unknown.
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    venue = Symbol(symbol).venue
    if venue is not None:
        phase = venue.phase(ts)
        if phase in _PHASE_TO_SESSION:
            return _PHASE_TO_SESSION[phase]
        if phase == "closed":
            prev_close = venue.previous_close(ts)
            next_open = venue.next_open(ts)
            if prev_close is not None and next_open is not None:
                return "post" if ts - prev_close <= next_open - ts else "pre"
            return "post"

    if tz_name:
        try:
            local = ts.astimezone(ZoneInfo(tz_name)).time()
        except Exception:
            local = None
        if local is not None:
            if local < time(9, 0):
                return "pre"
            if local >= time(17, 30):
                return "post"
            return "regular"

    local = ts.astimezone(ET).time()
    if local < time(9, 30):
        return "pre"
    if local >= time(16, 0):
        return "post"
    return "regular"


async def fetch_and_store_intraday(
    db: AsyncSession,
    symbols: list[str],
    asset_map: dict[str, int],
) -> int:
    """Fetch 1m intraday bars and upsert into the database. Returns row count.

    Before upserting, deletes bars older than the oldest bar in the fresh
    fetch so the DB only contains the current "1-day" window per asset.
    This prevents stale data from previous sessions mixing with today's data.

    The Yahoo fetch + currency normalisation happens in
    :meth:`YahooClient.intraday`; this function adds session classification
    (which depends on per-exchange trading hours) and persists.
    """
    raw = await yahoo_client.intraday(symbols)

    total = 0
    for sym, raw_bars in raw.items():
        bars = [
            {**b, "session": _classify_session(b["timestamp"], sym, b.get("tz_name"))}
            for b in raw_bars
        ]
        asset_id = asset_map.get(sym)
        if not asset_id or not bars:
            continue

        # Remove bars from previous sessions that Yahoo no longer returns
        oldest_ts = min(bar["timestamp"] for bar in bars)
        await db.execute(
            delete(IntradayPrice).where(
                IntradayPrice.asset_id == asset_id,
                IntradayPrice.timestamp < oldest_ts,
            )
        )

        rows = [
            {
                "asset_id": asset_id,
                "timestamp": bar["timestamp"],
                "price": bar["price"],
                "volume": bar["volume"],
                "session": bar["session"],
            }
            for bar in bars
        ]

        stmt = pg_insert(IntradayPrice).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["asset_id", "timestamp"],
            set_={
                "price": stmt.excluded.price,
                "volume": stmt.excluded.volume,
                "session": stmt.excluded.session,
            },
        )
        await db.execute(stmt)
        total += len(rows)

    await db.commit()
    return total


async def get_intraday_bars(
    db: AsyncSession,
    asset_ids: list[int],
    symbol_map: dict[int, str],
) -> dict[str, list[dict]]:
    """Read today's intraday bars from DB, keyed by symbol."""
    if not asset_ids:
        return {}

    # Fetch bars from last 2 days (covers pre-market + previous close)
    cutoff = datetime.now(ET).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)

    result = await db.execute(
        select(IntradayPrice)
        .where(
            IntradayPrice.asset_id.in_(asset_ids),
            IntradayPrice.timestamp >= cutoff,
        )
        .order_by(IntradayPrice.asset_id, IntradayPrice.timestamp)
    )
    rows = result.scalars().all()

    bars_by_symbol: dict[str, list[dict]] = {}
    for row in rows:
        sym = symbol_map.get(row.asset_id)
        if not sym:
            continue
        bars_by_symbol.setdefault(sym, []).append({
            "time": int(row.timestamp.timestamp()),
            "price": float(row.price),
            "volume": row.volume,
            "session": row.session,
        })

    return bars_by_symbol


async def cleanup_old_intraday(db: AsyncSession) -> int:
    """Delete intraday data older than 1 day. Returns rows deleted."""
    today = date.today()
    cutoff = datetime.combine(today - timedelta(days=1), time.min, tzinfo=ET)
    result = await db.execute(
        delete(IntradayPrice).where(IntradayPrice.timestamp < cutoff)
    )
    await db.commit()
    return result.rowcount or 0

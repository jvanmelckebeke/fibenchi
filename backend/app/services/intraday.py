"""Intraday price fetching, storage, and cleanup for live day view."""

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import cast
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AssetRef
from app.domain.phases import PHASE_TO_SESSION, Phase, Session
from app.models.intraday import IntradayPrice
from app.schemas.intraday import IntradayBar
from app.services.yahoo import yahoo_client

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


def _classify_session(ts: datetime, ref: AssetRef, tz_name: str | None = None) -> Session:
    """Classify a bar timestamp as pre/regular/post.

    Venue-schedule based (``ref.venue.phase``): holiday- and half-day-aware
    — the old hand-maintained wall-clock table filed bars after a 13:00 ET
    early close as "regular". Venues without extended hours can still print
    auction/late bars outside regular sessions; those "closed" instants are
    filed to the nearer session boundary (evening → post, next morning →
    pre) to preserve the 3-value storage.

    Fallback when no venue resolves: wall-clock against the bar's own
    exchange timezone with generic 09:00–17:30 hours, or US Eastern regular
    hours when even the timezone is unknown.
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    venue = ref.venue
    if venue is not None:
        phase = venue.phase(ts)
        if phase in PHASE_TO_SESSION:
            return PHASE_TO_SESSION[phase]
        if phase == Phase.CLOSED:
            prev_close = venue.previous_close(ts)
            next_open = venue.next_open(ts)
            if prev_close is not None and next_open is not None:
                return Session.POST if ts - prev_close <= next_open - ts else Session.PRE
            return Session.POST

    if tz_name:
        try:
            local = ts.astimezone(ZoneInfo(tz_name)).time()
        except Exception:
            local = None
        if local is not None:
            if local < time(9, 0):
                return Session.PRE
            if local >= time(17, 30):
                return Session.POST
            return Session.REGULAR

    local = ts.astimezone(ET).time()
    if local < time(9, 30):
        return Session.PRE
    if local >= time(16, 0):
        return Session.POST
    return Session.REGULAR


# One bind parameter per column per row against PostgreSQL's 32767 ceiling,
# but the binding constraint here is memory, not the ceiling: a backend's
# parse/plan context for one thousand-row VALUES list grows to ~250 MB and
# postgres never returns it to the OS, so a pooled connection stays that big
# for life. Three such connections plus shared_buffers is what walked the
# 1 GB container into the OOM killer.
INTRADAY_UPSERT_CHUNK_ROWS = 500


async def _load_stored_window(
    db: AsyncSession, asset_ids: list[int]
) -> dict[int, dict[datetime, tuple[float, int, str]]]:
    """Read every stored bar for these assets, keyed by asset then timestamp."""
    if not asset_ids:
        return {}
    result = await db.execute(
        select(
            IntradayPrice.asset_id,
            IntradayPrice.timestamp,
            IntradayPrice.price,
            IntradayPrice.volume,
            IntradayPrice.session,
        ).where(IntradayPrice.asset_id.in_(asset_ids))
    )
    stored: dict[int, dict[datetime, tuple[float, int, str]]] = {}
    for asset_id, ts, price, volume, session in result:
        stored.setdefault(asset_id, {})[ts] = (float(price), int(volume or 0), session)
    return stored


def _changed_rows(
    rows: list[dict], stored: dict[datetime, tuple[float, int, str]]
) -> list[dict]:
    """Keep only the rows whose stored counterpart is absent or different.

    A closed 1-minute bar never changes: the price is a close, the volume is
    settled, and the divisor that normalises it is a per-currency constant,
    not a live FX rate. Re-upserting the whole day every 60s therefore
    rewrote ~26,600 identical rows a minute. ON CONFLICT DO UPDATE is a
    delete-plus-insert in the heap, so that churn showed up as 50,167
    inserts and 52,177 deletes against 26,636 live rows, generating the WAL
    and the dead tuples behind it. It had already cost one incident before
    this one: the surrogate id's int32 sequence exhausted at ~20M values a
    day, because ON CONFLICT burns a sequence value per *attempted* row
    (migrations 0018/0019 dropped the id rather than slow the churn).

    Comparing against what is stored costs one indexed SELECT per poll and
    leaves only the handful of bars that genuinely moved.
    """
    changed = []
    for row in rows:
        prev = stored.get(row["timestamp"])
        if prev == (row["price"], row["volume"], row["session"]):
            continue
        changed.append(row)
    return changed


async def fetch_and_store_intraday(
    db: AsyncSession,
    refs: list[AssetRef],
) -> int:
    """Fetch 1m intraday bars and upsert into the database. Returns row count.

    Only bars that are new or whose values moved are written; see
    :func:`_changed_rows`. Bars older than the oldest bar in the fresh fetch
    are deleted so the DB only holds the current "1-day" window per asset.

    The Yahoo fetch + currency normalisation happens in
    :meth:`YahooClient.intraday`; this function adds session classification
    (which depends on per-exchange trading hours) and persists.
    """
    raw = await yahoo_client.intraday(list(refs))
    by_symbol = {ref.symbol: ref for ref in refs}

    fetched: list[tuple[int, AssetRef, list]] = []
    for sym, raw_bars in raw.items():
        ref = by_symbol.get(sym)
        if ref is None or ref.id is None or not raw_bars:
            continue
        fetched.append((ref.id, ref, raw_bars))

    if not fetched:
        return 0

    stored = await _load_stored_window(db, [asset_id for asset_id, _, _ in fetched])

    total = 0
    for asset_id, ref, raw_bars in fetched:
        stored_bars = stored.get(asset_id, {})

        # Remove bars from previous sessions that Yahoo no longer returns.
        # Skipped unless something is actually older, which is every poll but
        # the first after a session rollover.
        oldest_ts = min(bar.timestamp for bar in raw_bars)
        if any(ts < oldest_ts for ts in stored_bars):
            await db.execute(
                delete(IntradayPrice).where(
                    IntradayPrice.asset_id == asset_id,
                    IntradayPrice.timestamp < oldest_ts,
                )
            )

        rows = [
            {
                "asset_id": asset_id,
                "timestamp": bar.timestamp,
                "price": bar.price,
                "volume": bar.volume,
                "session": _classify_session(bar.timestamp, ref, bar.tz_name),
            }
            for bar in raw_bars
        ]
        rows = _changed_rows(rows, stored_bars)
        if not rows:
            continue

        for start in range(0, len(rows), INTRADAY_UPSERT_CHUNK_ROWS):
            chunk = rows[start:start + INTRADAY_UPSERT_CHUNK_ROWS]
            stmt = pg_insert(IntradayPrice).values(chunk)
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
    refs: list[AssetRef],
) -> dict[str, list[IntradayBar]]:
    """Read the current window of intraday bars from DB, keyed by symbol.

    The window spans since yesterday's midnight ET (covers pre-market and
    the previous close), not just today.
    """
    by_id = {ref.id: ref for ref in refs if ref.id is not None}
    if not by_id:
        return {}

    # Fetch bars from last 2 days (covers pre-market + previous close)
    cutoff = datetime.now(ET).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)

    result = await db.execute(
        select(IntradayPrice)
        .where(
            IntradayPrice.asset_id.in_(by_id),
            IntradayPrice.timestamp >= cutoff,
        )
        .order_by(IntradayPrice.asset_id, IntradayPrice.timestamp)
    )
    rows = result.scalars().all()

    bars_by_symbol: dict[str, list[IntradayBar]] = {}
    for row in rows:
        ref = by_id.get(row.asset_id)
        if ref is None:
            continue
        sym = ref.symbol
        bars_by_symbol.setdefault(sym, []).append(IntradayBar(
            time=int(row.timestamp.timestamp()),
            price=row.price,
            volume=row.volume,
            # DB column is str-typed but only ever stores the 3 session values
            # (written via _classify_session); Pydantic re-validates at runtime.
            session=cast(Session, row.session),
        ))

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

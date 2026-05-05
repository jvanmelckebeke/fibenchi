"""Intraday price fetching, storage, and cleanup for live day view."""

import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intraday import IntradayPrice
from app.services.yahoo import yahoo_client

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

# Exchange regular hours by timezone — (open, close) in local time.
# Used to classify intraday bars as pre/regular/post per exchange.
_EXCHANGE_HOURS: dict[str, tuple[time, time]] = {
    "America/New_York": (time(9, 30), time(16, 0)),
    "America/Chicago": (time(8, 30), time(15, 0)),
    "America/Toronto": (time(9, 30), time(16, 0)),
    "America/Sao_Paulo": (time(10, 0), time(17, 0)),
    "Europe/London": (time(8, 0), time(16, 30)),
    "Europe/Berlin": (time(9, 0), time(17, 30)),
    "Europe/Paris": (time(9, 0), time(17, 30)),
    "Europe/Amsterdam": (time(9, 0), time(17, 30)),
    "Europe/Brussels": (time(9, 0), time(17, 30)),
    "Europe/Zurich": (time(9, 0), time(17, 30)),
    "Europe/Madrid": (time(9, 0), time(17, 30)),
    "Europe/Milan": (time(9, 0), time(17, 30)),
    "Europe/Lisbon": (time(8, 0), time(16, 30)),
    "Europe/Dublin": (time(8, 0), time(16, 30)),
    "Europe/Copenhagen": (time(9, 0), time(17, 0)),
    "Europe/Oslo": (time(9, 0), time(16, 30)),
    "Europe/Stockholm": (time(9, 0), time(17, 30)),
    "Europe/Helsinki": (time(10, 0), time(18, 30)),
    "Europe/Warsaw": (time(9, 0), time(17, 0)),
    "Europe/Athens": (time(10, 0), time(17, 20)),
    "Europe/Istanbul": (time(10, 0), time(18, 0)),
    "Asia/Tokyo": (time(9, 0), time(15, 0)),
    "Asia/Hong_Kong": (time(9, 30), time(16, 0)),
    "Asia/Shanghai": (time(9, 30), time(15, 0)),
    "Asia/Seoul": (time(9, 0), time(15, 30)),
    "Asia/Kolkata": (time(9, 15), time(15, 30)),
    "Australia/Sydney": (time(10, 0), time(16, 0)),
}


def _classify_session(ts: datetime, tz_name: str | None = None) -> str:
    """Classify a timestamp into pre/regular/post based on exchange hours.

    Uses the exchange's timezone and regular trading hours when available,
    falls back to US Eastern Time for unknown exchanges.
    """
    if tz_name and tz_name in _EXCHANGE_HOURS:
        tz = ZoneInfo(tz_name)
        local_time = ts.astimezone(tz).time()
        open_time, close_time = _EXCHANGE_HOURS[tz_name]
    else:
        local_time = ts.astimezone(ET).time()
        open_time, close_time = time(9, 30), time(16, 0)

    if local_time < open_time:
        return "pre"
    if local_time >= close_time:
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
            {**b, "session": _classify_session(b["timestamp"], b.get("tz_name"))}
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
            constraint="uq_intraday_asset_ts",
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

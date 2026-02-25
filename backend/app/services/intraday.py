"""Intraday price fetching, storage, and cleanup for live day view."""

import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from yahooquery import Ticker

from app.models.intraday import IntradayPrice
from app.services.yahoo.currency import resolve_currency
from app.utils import async_threadable

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


@async_threadable
def _fetch_intraday_sync(symbols: list[str]) -> dict[str, list[dict]]:
    """Fetch 1-minute intraday bars from Yahoo Finance (blocking).

    Uses ``includePrePost=true`` so pre-market and post-market bars are
    included — without it Yahoo only returns the previous regular session.
    """
    if not symbols:
        return {}

    ticker = Ticker(symbols)
    price_data = ticker.price

    # yahooquery's history() doesn't expose includePrePost, so call the
    # internal chart endpoint directly with the flag enabled.
    params = {"range": "1d", "interval": "1m", "includePrePost": "true"}
    data = ticker._get_data("chart", params)
    hist = ticker._historical_data_to_dataframe(data, params, adj_timezone=True)

    if isinstance(hist, dict) or hist.empty:
        return {}

    result: dict[str, list[dict]] = {}
    for sym in symbols:
        try:
            if isinstance(hist.index, pd.MultiIndex):
                df = hist.loc[sym].copy()
            else:
                df = hist.copy()

            if df.empty:
                continue

            # Resolve currency divisor and exchange timezone for session classification
            info = price_data.get(sym, {}) if isinstance(price_data, dict) else {}
            _, divisor = resolve_currency(info, sym)
            tz_name = info.get("exchangeTimezoneName") if isinstance(info, dict) else None

            # Fall back to timezone from the first timestamp when Yahoo
            # doesn't provide exchangeTimezoneName (e.g. Copenhagen).
            if not tz_name and len(df) > 0:
                first_ts = pd.Timestamp(df.index[0])
                if first_ts.tzinfo is not None:
                    tz_name = str(first_ts.tzinfo)

            bars = []
            for idx, row in df.iterrows():
                ts = pd.Timestamp(idx)
                if ts.tzinfo is None:
                    ts = ts.tz_localize("America/New_York")
                dt = ts.to_pydatetime()

                # Yahoo's chart API returns synthetic "current price" echo
                # bars at non-minute-boundary timestamps (e.g. 10:03:43
                # instead of 10:03:00) with volume=0.  These pollute the
                # DB and can get mis-classified when the timezone context
                # differs between fetch cycles, causing wrong session
                # colors on European stocks.  All real 1m candles land on
                # exact minute boundaries, so drop the rest.
                if int(dt.timestamp()) % 60 != 0:
                    continue

                close_val = float(row["close"])
                if divisor != 1:
                    close_val = close_val / divisor

                bars.append({
                    "timestamp": dt,
                    "price": round(close_val, 4),
                    "volume": int(row["volume"]) if pd.notna(row.get("volume", None)) else 0,
                    "session": _classify_session(dt, tz_name),
                })

            if bars:
                result[sym] = bars
        except (KeyError, TypeError):
            continue

    return result


async def fetch_and_store_intraday(
    db: AsyncSession,
    symbols: list[str],
    asset_map: dict[str, int],
) -> int:
    """Fetch 1m intraday bars and upsert into the database. Returns row count.

    Before upserting, deletes bars older than the oldest bar in the fresh
    fetch so the DB only contains the current "1-day" window per asset.
    This prevents stale data from previous sessions mixing with today's data.
    """
    data = await _fetch_intraday_sync(symbols)

    total = 0
    for sym, bars in data.items():
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

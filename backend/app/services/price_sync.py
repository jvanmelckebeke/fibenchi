"""Sync price data from Yahoo Finance to the database."""

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, PriceHistory
from app.services.yahoo import fetch_history, batch_fetch_history


async def sync_asset_prices(db: AsyncSession, asset: Asset, period: str = "3mo") -> int:
    """Fetch and upsert price data for a single asset. Returns number of rows upserted."""
    df = fetch_history(asset.symbol, period=period)
    return await _upsert_prices(db, asset.id, df)


async def sync_all_prices(db: AsyncSession, period: str = "1y") -> dict[str, int]:
    """Fetch and upsert prices for all watchlist assets. Returns {symbol: count}."""
    result = await db.execute(select(Asset))
    assets = result.scalars().all()

    if not assets:
        return {}

    symbols = [a.symbol for a in assets]
    asset_map = {a.symbol: a.id for a in assets}
    data = batch_fetch_history(symbols, period=period)

    counts = {}
    for sym, df in data.items():
        asset_id = asset_map.get(sym)
        if asset_id:
            counts[sym] = await _upsert_prices(db, asset_id, df)

    return counts


async def _upsert_prices(db: AsyncSession, asset_id: int, df: pd.DataFrame) -> int:
    """Upsert price rows from a DataFrame. Returns row count."""
    if df.empty:
        return 0

    rows = []
    for idx, row in df.iterrows():
        dt = idx.date() if hasattr(idx, "date") else idx
        if not isinstance(dt, date):
            dt = pd.Timestamp(dt).date()

        rows.append({
            "asset_id": asset_id,
            "date": dt,
            "open": round(float(row["open"]), 4),
            "high": round(float(row["high"]), 4),
            "low": round(float(row["low"]), 4),
            "close": round(float(row["close"]), 4),
            "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
        })

    stmt = pg_insert(PriceHistory).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_asset_date",
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
        },
    )
    await db.execute(stmt)
    await db.commit()
    return len(rows)

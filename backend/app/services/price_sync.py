"""Sync price data from Yahoo Finance to the database."""

from datetime import date

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset
from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.services.yahoo import fetch_history, batch_fetch_history


async def sync_asset_prices(db: AsyncSession, asset: Asset, period: str = "3mo") -> int:
    """Fetch and upsert price data for a single asset. Returns number of rows upserted."""
    df = await fetch_history(asset.symbol, period=period)
    return await _upsert_prices(db, asset.id, df)


async def sync_asset_prices_range(
    db: AsyncSession, asset: Asset, start: date, end: date
) -> int:
    """Fetch and upsert price data for a date range. Returns number of rows upserted."""
    df = await fetch_history(asset.symbol, start=start, end=end)
    return await _upsert_prices(db, asset.id, df)


async def sync_all_prices(db: AsyncSession, period: str = "1y") -> dict[str, int]:
    """Fetch and upsert prices for all tracked assets. Returns {symbol: count}."""
    assets = await AssetRepository(db).list_all()

    if not assets:
        return {}

    symbols = [a.symbol for a in assets]
    asset_map = {a.symbol: a.id for a in assets}
    data = await batch_fetch_history(symbols, period=period)

    counts = {}
    for sym, df in data.items():
        asset_id = asset_map.get(sym)
        if asset_id:
            counts[sym] = await _upsert_prices(db, asset_id, df)

    return counts


async def _upsert_prices(db: AsyncSession, asset_id: int, df: pd.DataFrame) -> int:
    """Upsert price rows from a DataFrame. Returns row count."""
    return await PriceRepository(db).upsert_prices(asset_id, df)

"""Shared router dependencies and helpers."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset


async def find_asset(symbol: str, db: AsyncSession) -> Asset | None:
    """Look up asset in DB, returning None if not found."""
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    return result.scalar_one_or_none()


async def get_asset(symbol: str, db: AsyncSession) -> Asset:
    """Look up asset in DB, raising 404 if not found."""
    asset = await find_asset(symbol, db)
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")
    return asset

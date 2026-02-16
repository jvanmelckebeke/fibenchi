"""Shared router dependencies and helpers."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Group
from app.models.pseudo_etf import PseudoETF


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


async def get_pseudo_etf(etf_id: int, db: AsyncSession) -> PseudoETF:
    """Look up pseudo-ETF by ID, raising 404 if not found."""
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")
    return etf


async def get_group(group_id: int, db: AsyncSession) -> Group:
    """Look up group by ID, raising 404 if not found."""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")
    return group

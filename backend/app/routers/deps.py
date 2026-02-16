"""Shared router dependencies and helpers."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Group
from app.models.pseudo_etf import PseudoETF
from app.repositories.asset_repo import AssetRepository
from app.repositories.group_repo import GroupRepository
from app.repositories.pseudo_etf_repo import PseudoEtfRepository


async def find_asset(symbol: str, db: AsyncSession) -> Asset | None:
    """Look up asset in DB, returning None if not found."""
    return await AssetRepository(db).find_by_symbol(symbol)


async def get_asset(symbol: str, db: AsyncSession) -> Asset:
    """Look up asset in DB, raising 404 if not found."""
    asset = await find_asset(symbol, db)
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")
    return asset


async def get_pseudo_etf(etf_id: int, db: AsyncSession) -> PseudoETF:
    """Look up pseudo-ETF by ID, raising 404 if not found."""
    etf = await PseudoEtfRepository(db).get_by_id(etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")
    return etf


async def get_group(group_id: int, db: AsyncSession) -> Group:
    """Look up group by ID, raising 404 if not found."""
    group = await GroupRepository(db).get_by_id(group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    return group

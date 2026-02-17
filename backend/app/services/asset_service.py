from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssetType
from app.repositories.asset_repo import AssetRepository
from app.services.lookups import get_asset
from app.services.yahoo import validate_symbol


async def list_assets(db: AsyncSession):
    return await AssetRepository(db).list_watchlisted()


async def create_asset(db: AsyncSession, symbol: str, name: str | None, asset_type: AssetType, watchlisted: bool):
    repo = AssetRepository(db)
    symbol = symbol.upper()

    existing = await repo.find_by_symbol(symbol)
    if existing:
        if not existing.watchlisted and watchlisted:
            existing.watchlisted = True
            return await repo.save(existing)
        raise HTTPException(400, f"Asset with symbol {symbol} already exists")

    currency = "USD"
    if not name:
        info = await validate_symbol(symbol)
        if not info:
            raise HTTPException(404, f"Symbol {symbol} not found on Yahoo Finance")
        name = info["name"]
        currency = info.get("currency", "USD")
        if info["type"] == "ETF":
            asset_type = AssetType.ETF

    return await repo.create(
        symbol=symbol, name=name, type=asset_type, watchlisted=watchlisted, currency=currency,
    )


async def delete_asset(db: AsyncSession, symbol: str):
    asset = await get_asset(symbol, db)
    asset.watchlisted = False
    await AssetRepository(db).save(asset)

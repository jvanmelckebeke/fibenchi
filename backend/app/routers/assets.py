from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Asset, AssetType
from app.schemas.asset import AssetCreate, AssetResponse
from app.services.yahoo import validate_symbol

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("", response_model=list[AssetResponse])
async def list_assets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asset).order_by(Asset.symbol))
    return result.scalars().all()


@router.post("", response_model=AssetResponse, status_code=201)
async def create_asset(data: AssetCreate, db: AsyncSession = Depends(get_db)):
    symbol = data.symbol.upper()

    existing = await db.execute(select(Asset).where(Asset.symbol == symbol))
    asset = existing.scalar_one_or_none()
    if asset:
        if not asset.watchlisted and data.watchlisted:
            asset.watchlisted = True
            await db.commit()
            await db.refresh(asset)
            return asset
        raise HTTPException(400, f"Asset with symbol {symbol} already exists")

    name = data.name
    asset_type = data.type

    if not name:
        info = validate_symbol(symbol)
        if not info:
            raise HTTPException(404, f"Symbol {symbol} not found on Yahoo Finance")
        name = info["name"]
        if info["type"] == "ETF":
            asset_type = AssetType.ETF

    asset = Asset(symbol=symbol, name=name, type=asset_type, watchlisted=data.watchlisted)
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


@router.delete("/{symbol}", status_code=204)
async def delete_asset(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")
    asset.watchlisted = False
    await db.commit()

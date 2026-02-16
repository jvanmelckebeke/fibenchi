from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Asset, AssetType
from app.routers.deps import get_asset
from app.schemas.asset import AssetCreate, AssetResponse
from app.services.yahoo import validate_symbol

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("", response_model=list[AssetResponse], summary="List watchlisted assets")
async def list_assets(db: AsyncSession = Depends(get_db)):
    """Return all assets where `watchlisted=true`, ordered alphabetically by symbol."""
    result = await db.execute(
        select(Asset).where(Asset.watchlisted == True).order_by(Asset.symbol)  # noqa: E712
    )
    return result.scalars().all()


@router.post("", response_model=AssetResponse, status_code=201, summary="Add an asset to the watchlist")
async def create_asset(data: AssetCreate, db: AsyncSession = Depends(get_db)):
    """Add a new asset by ticker symbol. The symbol is validated against Yahoo Finance
    which also auto-detects the asset name, type (stock/etf), and currency.

    If the symbol already exists but was previously soft-deleted, it is re-watchlisted.
    """
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
    currency = "USD"

    if not name:
        info = await validate_symbol(symbol)
        if not info:
            raise HTTPException(404, f"Symbol {symbol} not found on Yahoo Finance")
        name = info["name"]
        currency = info.get("currency", "USD")
        if info["type"] == "ETF":
            asset_type = AssetType.ETF

    asset = Asset(symbol=symbol, name=name, type=asset_type, watchlisted=data.watchlisted, currency=currency)
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


@router.delete("/{symbol}", status_code=204, summary="Soft-delete an asset from the watchlist")
async def delete_asset(symbol: str, db: AsyncSession = Depends(get_db)):
    """Set `watchlisted=false` on the asset. The row is preserved so that
    pseudo-ETF constituent relationships remain intact.
    """
    asset = await get_asset(symbol, db)
    asset.watchlisted = False
    await db.commit()

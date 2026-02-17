from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.asset import AssetCreate, AssetResponse
from app.services import asset_service

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("", response_model=list[AssetResponse], summary="List watchlisted assets")
async def list_assets(db: AsyncSession = Depends(get_db)):
    """Return all assets where `watchlisted=true`, ordered alphabetically by symbol."""
    return await asset_service.list_assets(db)


@router.post("", response_model=AssetResponse, status_code=201, summary="Add an asset to the watchlist")
async def create_asset(data: AssetCreate, db: AsyncSession = Depends(get_db)):
    """Add a new asset by ticker symbol. The symbol is validated against Yahoo Finance
    which also auto-detects the asset name, type (stock/etf), and currency.

    If the symbol already exists but was previously soft-deleted, it is re-watchlisted.
    """
    return await asset_service.create_asset(db, data.symbol, data.name, data.type, data.watchlisted)


@router.delete("/{symbol}", status_code=204, summary="Soft-delete an asset from the watchlist")
async def delete_asset(symbol: str, db: AsyncSession = Depends(get_db)):
    """Set `watchlisted=false` on the asset. The row is preserved so that
    pseudo-ETF constituent relationships remain intact.
    """
    await asset_service.delete_asset(db, symbol)

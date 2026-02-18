from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.asset import AssetCreate, AssetResponse
from app.services import asset_service

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("", response_model=list[AssetResponse], summary="List grouped assets")
async def list_assets(db: AsyncSession = Depends(get_db)):
    """Return all assets that belong to at least one group, ordered alphabetically by symbol."""
    return await asset_service.list_assets(db)


@router.post("", response_model=AssetResponse, status_code=201, summary="Add an asset")
async def create_asset(data: AssetCreate, db: AsyncSession = Depends(get_db)):
    """Add a new asset by ticker symbol. The symbol is validated against Yahoo Finance
    which also auto-detects the asset name, type (stock/etf), and currency.

    By default the asset is added to the Watchlist group. Set `add_to_watchlist=false`
    to create the asset record without group membership (e.g. for pseudo-ETF constituents).
    """
    return await asset_service.create_asset(db, data.symbol, data.name, data.type, data.add_to_watchlist)


@router.delete("/{symbol}", status_code=204, summary="Remove an asset from the watchlist")
async def delete_asset(symbol: str, db: AsyncSession = Depends(get_db)):
    """Remove the asset from the default Watchlist group. The row is preserved so that
    pseudo-ETF constituent relationships remain intact.
    """
    await asset_service.delete_asset(db, symbol)

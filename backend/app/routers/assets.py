from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.asset import AssetAttachments, AssetCreate, AssetResponse, AssetUpdate
from app.services import asset_service

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("", response_model=list[AssetResponse], summary="List all assets")
async def list_assets(db: AsyncSession = Depends(get_db)):
    """Return all assets, ordered alphabetically by symbol.

    Includes assets not attached to any group — newly-created assets are orphans
    until ``POST /api/groups/{id}/assets`` attaches them. Internal views that need
    only grouped assets use repository-level filters directly.
    """
    return await asset_service.list_assets(db)


@router.post("", response_model=AssetResponse, status_code=201, summary="Add an asset")
async def create_asset(data: AssetCreate, db: AsyncSession = Depends(get_db)):
    """Add a new asset by ticker symbol. The symbol is validated against Yahoo Finance
    which also auto-detects the asset name, type (stock/etf), and currency.

    The asset is created without group membership. Use
    ``POST /api/groups/{id}/assets`` afterwards to attach it to the Watchlist
    or any other group.
    """
    return await asset_service.create_asset(db, data.symbol, data.name, data.type)


@router.patch("/{asset_id}", response_model=AssetResponse, summary="Update asset metadata")
async def update_asset(asset_id: int, data: AssetUpdate, db: AsyncSession = Depends(get_db)):
    """Patch an asset's metadata (name, type, currency). Useful for reclassifying
    a ticker (e.g. stock → index) or fixing an incorrect auto-detected currency.
    Fields omitted from the request body are left untouched.
    """
    return await asset_service.update_asset(
        db,
        asset_id,
        name=data.name,
        asset_type=data.type,
        currency=data.currency,
    )


@router.get(
    "/{symbol}/attachments",
    response_model=AssetAttachments,
    summary="Summarise what is attached to an asset",
)
async def get_asset_attachments(symbol: str, db: AsyncSession = Depends(get_db)):
    """Return the asset's group / pseudo-ETF / thesis memberships, tags, note and
    annotation count. The remove dialog uses this to warn before leaving the asset
    in zero groups, and to show what a hard delete would cascade into.
    """
    return await asset_service.get_attachments(db, symbol)


@router.delete("/{symbol}", status_code=204, summary="Remove an asset (soft) or delete it entirely (hard)")
async def delete_asset(
    symbol: str,
    hard: bool = Query(
        default=False,
        description="If true, permanently delete the asset row and cascade "
        "(group + pseudo-ETF + thesis memberships, tags, note, annotations, prices). "
        "Default false only removes it from the default group, preserving the row.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Remove the asset from the default group (soft, the row is preserved so
    pseudo-ETF constituent relationships remain intact), or — with ``hard=true`` —
    permanently delete the asset and everything attached to it.
    """
    if hard:
        await asset_service.hard_delete_asset(db, symbol)
    else:
        await asset_service.delete_asset(db, symbol)

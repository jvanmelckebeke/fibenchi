from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.asset import (
    AssetAttachments,
    AssetCreate,
    AssetDetectionReset,
    AssetResponse,
    AssetUpdate,
)
from app.services import asset_service
from app.services.asset_suggestion import suggest_for_asset

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _with_suggestion(asset):
    """Attach Fibenchi's read on the row, for ``AssetResponse.suggested``.

    A transient attribute rather than a column, and attached here rather than
    in the service because it is a presentation concern: the suggestion is
    re-derived on every read so it can never go stale, and is never written —
    the whole point is that stored values change only when a user applies one.
    """
    asset.suggested = suggest_for_asset(asset)
    return asset


@router.get("", response_model=list[AssetResponse], summary="List all assets")
async def list_assets(db: AsyncSession = Depends(get_db)):
    """Return all assets, ordered alphabetically by symbol.

    Includes assets not attached to any group — newly-created assets are orphans
    until ``POST /api/groups/{id}/assets`` attaches them. Internal views that need
    only grouped assets use repository-level filters directly.
    """
    return [_with_suggestion(a) for a in await asset_service.list_assets(db)]


@router.post("", response_model=AssetResponse, status_code=201, summary="Add an asset")
async def create_asset(data: AssetCreate, db: AsyncSession = Depends(get_db)):
    """Add a new asset by ticker symbol. The symbol is validated against Yahoo Finance
    which also auto-detects the asset name, type (stock/etf), and currency.

    The asset is created without group membership. Use
    ``POST /api/groups/{id}/assets`` afterwards to attach it to the Watchlist
    or any other group.
    """
    return _with_suggestion(await asset_service.create_asset(db, data.symbol, data.name, data.type))


@router.patch("/{asset_id}", response_model=AssetResponse, summary="Update asset metadata")
async def update_asset(asset_id: int, data: AssetUpdate, db: AsyncSession = Depends(get_db)):
    """Patch an asset's metadata (name, type, currency, unit_kind). Useful for
    reclassifying a ticker (e.g. stock → index), fixing an auto-detected
    currency, or saying how the price number reads. Fields omitted from the
    request body are left untouched.

    Any field supplied is recorded as *your* choice, so Fibenchi stops
    suggesting alternatives for it — see ``suggested`` on the response.
    """
    return _with_suggestion(await asset_service.update_asset(
        db,
        asset_id,
        name=data.name,
        asset_type=data.type,
        currency=data.currency,
        unit_kind=data.unit_kind,
    ))


@router.post(
    "/{asset_id}/reset-detection",
    response_model=AssetResponse,
    summary="Hand classification fields back to auto-detection",
)
async def reset_detection(asset_id: int, data: AssetDetectionReset, db: AsyncSession = Depends(get_db)):
    """Adopt Fibenchi's read for the named fields and clear their user flag, so
    they track future improvements again.

    The inverse of a PATCH: editing says "I've decided", this says "you decide".
    ``currency`` is never reset — the shape's currency is a venue-suffix fallback,
    weaker than Yahoo's, and inert once the unit says the number isn't money.
    """
    return _with_suggestion(
        await asset_service.reset_asset_detection(db, asset_id, set(data.fields))
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

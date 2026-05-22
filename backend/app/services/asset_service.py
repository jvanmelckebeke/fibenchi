from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, AssetType
from app.repositories.asset_repo import AssetRepository
from app.repositories.group_repo import GroupRepository
from app.services.currency_service import ensure_currency
from app.services.entity_lookups import get_asset
from app.services.yahoo import currency_from_suffix, yahoo_client


async def list_assets(db: AsyncSession):
    return await AssetRepository(db).list_all()


async def create_asset(
    db: AsyncSession,
    symbol: str,
    name: str | None,
    asset_type: AssetType,
):
    """Create an asset row. Group attachment is the caller's responsibility —
    use ``POST /api/groups/{id}/assets`` afterwards to put it in a group
    (Watchlist or otherwise)."""
    repo = AssetRepository(db)
    symbol = symbol.upper()

    existing = await repo.find_by_symbol(symbol)
    if existing:
        return existing

    info = await yahoo_client.validate(symbol)
    if not info:
        if not name:
            raise HTTPException(404, f"Symbol {symbol} not found on Yahoo Finance")
        currency = currency_from_suffix(symbol) or "USD"
    else:
        currency = info.get("currency_code") or info.get("currency", "USD")
        if not name:
            name = info["name"]
        if info["type"] == "ETF":
            asset_type = AssetType.ETF
        elif info["type"] == "INDEX":
            asset_type = AssetType.INDEX

    await ensure_currency(db, currency)
    return await repo.create(
        symbol=symbol, name=name, type=asset_type, currency=currency,
    )


async def update_asset(
    db: AsyncSession,
    asset_id: int,
    name: str | None = None,
    asset_type: AssetType | None = None,
    currency: str | None = None,
):
    """Apply partial updates to an asset row (name, type, currency).

    Lets users reclassify a ticker after the fact (e.g. flip an index that
    was auto-detected as a stock to ``AssetType.INDEX``) and override the
    Yahoo-derived currency. None-valued fields are left untouched.
    """
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, f"Asset {asset_id} not found")

    if name is not None:
        asset.name = name
    if asset_type is not None:
        asset.type = asset_type
    if currency is not None:
        await ensure_currency(db, currency)
        asset.currency = currency

    return await AssetRepository(db).save(asset)


async def delete_asset(db: AsyncSession, symbol: str):
    """Remove an asset from the default group (soft-delete).

    The asset row is preserved so that pseudo-ETF constituent relationships
    remain intact.
    """
    asset = await get_asset(symbol, db)
    group_repo = GroupRepository(db)
    default_group = await group_repo.get_default()
    if default_group is None:
        raise HTTPException(
            500,
            "No default group is configured. Set is_default=true on exactly one "
            "group (typically 'Watchlist'). Migration 0014 repairs this on deploy.",
        )
    default_group.assets = [a for a in default_group.assets if a.id != asset.id]
    await group_repo.save(default_group)

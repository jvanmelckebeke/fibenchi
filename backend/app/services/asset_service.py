from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssetType
from app.repositories.asset_repo import AssetRepository
from app.repositories.group_repo import GroupRepository
from app.services.currency_service import ensure_currency
from app.services.entity_lookups import get_asset
from app.services.yahoo import validate_symbol


async def list_assets(db: AsyncSession):
    return await AssetRepository(db).list_in_any_group()


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

    info = await validate_symbol(symbol)
    if not info:
        if not name:
            raise HTTPException(404, f"Symbol {symbol} not found on Yahoo Finance")
        from app.services.yahoo import currency_from_suffix
        currency = currency_from_suffix(symbol) or "USD"
    else:
        currency = info.get("currency_code") or info.get("currency", "USD")
        if not name:
            name = info["name"]
        if info["type"] == "ETF":
            asset_type = AssetType.ETF

    await ensure_currency(db, currency)
    return await repo.create(
        symbol=symbol, name=name, type=asset_type, currency=currency,
    )


async def delete_asset(db: AsyncSession, symbol: str):
    """Remove an asset from the default group (soft-delete).

    The asset row is preserved so that pseudo-ETF constituent relationships
    remain intact.
    """
    asset = await get_asset(symbol, db)
    group_repo = GroupRepository(db)
    default_group = await group_repo.get_default()
    if default_group:
        default_group.assets = [a for a in default_group.assets if a.id != asset.id]
        await group_repo.save(default_group)

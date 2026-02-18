from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssetType
from app.repositories.asset_repo import AssetRepository
from app.repositories.group_repo import GroupRepository
from app.services.entity_lookups import get_asset
from app.services.yahoo import validate_symbol


async def list_assets(db: AsyncSession):
    return await AssetRepository(db).list_in_any_group()


async def create_asset(
    db: AsyncSession,
    symbol: str,
    name: str | None,
    asset_type: AssetType,
    add_to_watchlist: bool = True,
):
    repo = AssetRepository(db)
    symbol = symbol.upper()

    existing = await repo.find_by_symbol(symbol)
    if existing:
        if add_to_watchlist:
            # Add to default group if not already in it
            group_repo = GroupRepository(db)
            default_group = await group_repo.get_default()
            if default_group and existing.id not in {a.id for a in default_group.assets}:
                default_group.assets.append(existing)
                await group_repo.save(default_group)
            return existing
        # Caller just needs the asset record (e.g. pseudo-ETF constituent picker)
        return existing

    currency = "USD"
    if not name:
        info = await validate_symbol(symbol)
        if not info:
            raise HTTPException(404, f"Symbol {symbol} not found on Yahoo Finance")
        name = info["name"]
        currency = info.get("currency", "USD")
        if info["type"] == "ETF":
            asset_type = AssetType.ETF

    asset = await repo.create(
        symbol=symbol, name=name, type=asset_type, currency=currency,
    )

    if add_to_watchlist:
        group_repo = GroupRepository(db)
        default_group = await group_repo.get_default()
        if default_group:
            default_group.assets.append(asset)
            await group_repo.save(default_group)

    return asset


async def delete_asset(db: AsyncSession, symbol: str):
    """Remove an asset from the default Watchlist group (soft-delete).

    The asset row is preserved so that pseudo-ETF constituent relationships
    remain intact.
    """
    asset = await get_asset(symbol, db)
    group_repo = GroupRepository(db)
    default_group = await group_repo.get_default()
    if default_group:
        default_group.assets = [a for a in default_group.assets if a.id != asset.id]
        await group_repo.save(default_group)

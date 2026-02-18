from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssetType
from app.repositories.asset_repo import AssetRepository
from app.repositories.group_repo import GroupRepository
from app.services.currency_service import ensure_currency, lookup as currency_lookup
from app.services.entity_lookups import get_asset
from app.services.yahoo import validate_symbol


async def list_assets(db: AsyncSession):
    return await AssetRepository(db).list_in_any_group()


async def create_asset(
    db: AsyncSession,
    symbol: str,
    name: str | None,
    asset_type: AssetType,
    add_to_default_group: bool = True,
):
    repo = AssetRepository(db)
    symbol = symbol.upper()

    existing = await repo.find_by_symbol(symbol)
    if existing:
        if add_to_default_group:
            # Add to default group if not already in it
            group_repo = GroupRepository(db)
            default_group = await group_repo.get_default()
            if default_group and existing.id not in {a.id for a in default_group.assets}:
                default_group.assets.append(existing)
                await group_repo.save(default_group)
            return existing
        # Caller just needs the asset record (e.g. pseudo-ETF constituent picker)
        return existing

    # Always call validate_symbol to detect currency (and name/type if not provided)
    info = await validate_symbol(symbol)
    if not info:
        if not name:
            raise HTTPException(404, f"Symbol {symbol} not found on Yahoo Finance")
        # Name was provided manually — proceed with exchange-suffix currency fallback
        from app.services.yahoo import _currency_from_suffix
        currency = _currency_from_suffix(symbol) or "USD"
    else:
        # Store raw Yahoo currency code (e.g. "GBp") — the currencies table
        # provides display_code and divisor via lookup.
        currency = info.get("currency_code") or info.get("currency", "USD")
        if not name:
            name = info["name"]
        if info["type"] == "ETF":
            asset_type = AssetType.ETF

    await ensure_currency(db, currency)
    asset = await repo.create(
        symbol=symbol, name=name, type=asset_type, currency=currency,
    )

    if add_to_default_group:
        group_repo = GroupRepository(db)
        default_group = await group_repo.get_default()
        if default_group:
            default_group.assets.append(asset)
            await group_repo.save(default_group)

    return asset


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

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AssetRef
from app.models import (
    Annotation,
    Asset,
    AssetType,
    Group,
    Note,
    PseudoETF,
    group_assets,
    pseudo_etf_constituents,
)
from app.repositories.asset_repo import AssetRepository
from app.repositories.group_repo import GroupRepository
from app.schemas.asset import AssetAttachments
from app.services.currency_service import ensure_currency
from app.services.entity_lookups import get_asset
from app.services.yahoo import yahoo_client


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

    ref = AssetRef(symbol)
    info = await yahoo_client.validate(symbol)
    if not info:
        if not name:
            raise HTTPException(404, f"Symbol {symbol} not found on Yahoo Finance")
        currency = ref.currency or "USD"
    else:
        currency = info.get("currency_code") or info.get("currency", "USD")
        if not name:
            name = info["name"]
        if info["type"] == "ETF":
            asset_type = AssetType.ETF
        elif info["type"] == "INDEX":
            asset_type = AssetType.INDEX

    # Shape has the last word on index-ness. Yahoo's quoteType is a live lookup
    # resolved once and then frozen in the row, and it has already been wrong:
    # ^GSPC, ^N225 and four others landed as stock and rendered with a currency
    # symbol ever since. classify() answers the same question from the ticker
    # alone, deterministically and offline, so it can't disagree with itself
    # later. Yahoo stays authoritative for ETF-vs-stock, which shape can't see.
    if ref.kind.is_index:
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


async def get_attachments(db: AsyncSession, symbol: str) -> AssetAttachments:
    """Summarise what is attached to an asset so the remove dialog can warn the
    user before an orphan (leaving zero groups) or a hard delete."""
    asset = await get_asset(symbol, db)  # tags/theses eager-loaded (lazy="selectin")

    group_names = (
        await db.execute(
            select(Group.name)
            .join(group_assets, Group.id == group_assets.c.group_id)
            .where(group_assets.c.asset_id == asset.id)
            .order_by(Group.name)
        )
    ).scalars().all()
    pseudo_names = (
        await db.execute(
            select(PseudoETF.name)
            .join(pseudo_etf_constituents, PseudoETF.id == pseudo_etf_constituents.c.pseudo_etf_id)
            .where(pseudo_etf_constituents.c.asset_id == asset.id)
            .order_by(PseudoETF.name)
        )
    ).scalars().all()
    note_content = (
        await db.execute(select(Note.content).where(Note.asset_id == asset.id))
    ).scalar_one_or_none()
    annotation_count = (
        await db.execute(select(func.count()).select_from(Annotation).where(Annotation.asset_id == asset.id))
    ).scalar_one()

    return AssetAttachments(
        symbol=asset.symbol,
        groups=list(group_names),
        theses=sorted(t.name for t in asset.theses),
        pseudo_etfs=list(pseudo_names),
        tags=sorted(t.name for t in asset.tags),
        has_note=bool(note_content and note_content.strip()),
        annotation_count=annotation_count,
    )


async def hard_delete_asset(db: AsyncSession, symbol: str):
    """Permanently delete the asset row and everything attached to it: group and
    pseudo-ETF memberships, thesis memberships, tags, note, annotations, prices,
    intraday bars.

    This is the explicit lifecycle choice offered in the remove dialog — distinct
    from the soft ``delete_asset`` (default-group only). A single Core ``DELETE``
    on the asset relies on the ``ON DELETE CASCADE`` every dependent FK declares,
    so the database clears the dependent rows in one statement (no ORM cascade, so
    nothing lazy-loads during flush). Tests enforce SQLite FK cascade to match
    Postgres (see ``conftest``), so this path is exercised the same everywhere.
    """
    asset = await get_asset(symbol, db)
    aid = asset.id
    # Detach the ORM object so a stale identity-map entry can't try to manage the
    # row we're deleting out from under it.
    db.expunge(asset)
    await db.execute(delete(Asset).where(Asset.id == aid))
    await db.commit()

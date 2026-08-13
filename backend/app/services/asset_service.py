from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AssetRef, UnitKind
from app.domain.provenance import FieldSource
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
from app.services.asset_suggestion import suggest_for
from app.services.currency_service import ensure_currency
from app.services.entity_lookups import get_asset
from app.services.yahoo import yahoo_client


async def list_assets(db: AsyncSession):
    return await AssetRepository(db).list_all()


async def create_asset(
    db: AsyncSession,
    symbol: str,
    name: str | None,
    asset_type: AssetType | None = None,
):
    """Create an asset row. Group attachment is the caller's responsibility —
    use ``POST /api/groups/{id}/assets`` afterwards to put it in a group
    (Watchlist or otherwise).

    ``asset_type`` None means "you decide" and is recorded as AUTO; an
    explicit value is a human's call and is recorded as USER, which keeps
    later suggestions quiet about it. The two were indistinguishable while
    the schema defaulted to STOCK.
    """
    repo = AssetRepository(db)
    symbol = symbol.upper()

    existing = await repo.find_by_symbol(symbol)
    if existing:
        return existing

    ref = AssetRef(symbol)
    suggestion = suggest_for(ref)
    info = await yahoo_client.validate(symbol)
    if not info:
        if not name:
            raise HTTPException(404, f"Symbol {symbol} not found on Yahoo Finance")
        currency = ref.currency or "USD"
        detected = suggestion.type
    else:
        currency = info.get("currency_code") or info.get("currency", "USD")
        if not name:
            name = info["name"]
        # Yahoo owns the ETF/stock call — shape can't see that distinction —
        # but shape owns index-ness, because quoteType is a live lookup frozen
        # into the row and it has already been wrong (see migration 0020).
        detected = AssetType.ETF if info["type"] == "ETF" else suggestion.type

    await ensure_currency(db, currency)
    return await repo.create(
        symbol=symbol,
        name=name,
        type=asset_type or detected,
        type_source=FieldSource.AUTO if asset_type is None else FieldSource.USER,
        currency=currency,
        unit_kind=suggestion.unit_kind,
        unit_source=FieldSource.AUTO,
    )


async def update_asset(
    db: AsyncSession,
    asset_id: int,
    name: str | None = None,
    asset_type: AssetType | None = None,
    currency: str | None = None,
    unit_kind: UnitKind | None = None,
):
    """Apply partial updates to an asset row (name, type, currency, unit).

    Lets users reclassify a ticker after the fact and override the
    Yahoo-derived currency or unit. None-valued fields are left untouched.

    Touching a field marks it USER, which is what stops Fibenchi from
    suggesting against it afterwards — the point isn't that the value is
    right, it's that a human decided it. ``unit_source`` covers both
    ``unit_kind`` and ``currency``: they answer one question together, so
    setting either means the caller has taken over the whole answer.
    """
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, f"Asset {asset_id} not found")

    if name is not None:
        asset.name = name
    if asset_type is not None:
        asset.type = asset_type
        asset.type_source = FieldSource.USER
    if currency is not None:
        await ensure_currency(db, currency)
        asset.currency = currency
        asset.unit_source = FieldSource.USER
    if unit_kind is not None:
        asset.unit_kind = unit_kind
        asset.unit_source = FieldSource.USER

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

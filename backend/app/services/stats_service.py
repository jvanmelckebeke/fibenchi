"""Collection stats + data-health assembly for the stats page."""

from collections import Counter

from fastapi import HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.background_tasks.price_heal import (
    HOLE_SCAN_WINDOW_DAYS,
    MAX_HOLE_HEALS_PER_SCAN,
    next_hole_scan_in_seconds,
    scan_session_coverage,
)
from app.domain import AssetRef
from app.models import (
    Annotation,
    Asset,
    Group,
    IntradayPrice,
    PriceHistory,
    PseudoETF,
    SymbolDirectory,
    Tag,
    group_assets,
)
from app.models.asset import AssetType
from app.models.pseudo_etf import pseudo_etf_constituents
from app.models.thesis import Thesis, thesis_assets
from app.schemas.system import DataHealthResponse, HoleSymbol, OrphanAsset, StatsResponse


async def _count(db: AsyncSession, entity) -> int:
    return (await db.execute(select(func.count()).select_from(entity))).scalar_one()


def _mix_bucket(symbol: str, asset_type: AssetType) -> str:
    """One-dimensional asset-mix bucket, combining the two classifications:
    ``AssetRef.kind`` (ticker shape — knows crypto/futures/fx, but files ETFs
    as plain equity) refined by the stored ``AssetType`` (Yahoo metadata —
    the only source that can tell an ETF from a stock)."""
    kind = AssetRef(symbol).kind
    if kind.is_crypto:
        return "crypto"
    if kind.is_future:
        return "futures"
    if kind.is_fx:
        return "fx"
    if kind.is_index or asset_type == AssetType.INDEX:
        return "indexes"
    if asset_type == AssetType.ETF:
        return "etfs"
    return "stocks"


async def collect_stats(db: AsyncSession) -> StatsResponse:
    """Collection-size numbers: how much data the instance has accumulated."""
    asset_rows = (await db.execute(select(Asset.symbol, Asset.type))).all()
    mix = Counter(_mix_bucket(sym, typ) for sym, typ in asset_rows)

    tracked = (
        await db.execute(select(func.count(distinct(group_assets.c.asset_id))))
    ).scalar_one()

    # Ungrouped assets split by *why* their row still exists: referenced by a
    # thesis or pseudo-ETF (the soft delete keeps these on purpose) vs
    # orphaned (referenced by nothing).
    in_group = select(group_assets.c.asset_id).where(group_assets.c.asset_id == Asset.id)
    referenced = (
        select(thesis_assets.c.asset_id).where(thesis_assets.c.asset_id == Asset.id)
    ).exists() | (
        select(pseudo_etf_constituents.c.asset_id).where(
            pseudo_etf_constituents.c.asset_id == Asset.id
        )
    ).exists()
    ungrouped_referenced = (
        await db.execute(
            select(func.count()).select_from(Asset).where(~in_group.exists(), referenced)
        )
    ).scalar_one()
    ungrouped_orphaned = (
        await db.execute(
            select(func.count()).select_from(Asset).where(~in_group.exists(), ~referenced)
        )
    ).scalar_one()

    earliest, latest = (
        await db.execute(select(func.min(PriceHistory.date), func.max(PriceHistory.date)))
    ).one()

    return StatsResponse(
        assets_total=len(asset_rows),
        assets_tracked=tracked,
        assets_thesis_or_etf_only=ungrouped_referenced,
        assets_orphaned=ungrouped_orphaned,
        stocks=mix["stocks"],
        etfs=mix["etfs"],
        indexes=mix["indexes"],
        crypto=mix["crypto"],
        futures=mix["futures"],
        fx=mix["fx"],
        price_bars=await _count(db, PriceHistory),
        earliest_bar=earliest,
        latest_bar=latest,
        collected_days=(latest - earliest).days + 1 if earliest and latest else 0,
        intraday_bars=await _count(db, IntradayPrice),
        groups=await _count(db, Group),
        pseudo_etfs=await _count(db, PseudoETF),
        theses=await _count(db, Thesis),
        tags=await _count(db, Tag),
        annotations=await _count(db, Annotation),
        symbol_directory_entries=await _count(db, SymbolDirectory),
    )


async def collect_data_health(db: AsyncSession) -> DataHealthResponse:
    """Session-coverage quality + self-heal status, from the same scan the
    heal itself uses."""
    coverage = await scan_session_coverage(db)
    with_holes = [(ref, holes) for ref, _, holes in coverage if holes]
    with_holes.sort(key=lambda c: max(c[1]), reverse=True)
    return DataHealthResponse(
        hole_symbols=[
            HoleSymbol(symbol=ref, missing_sessions=sorted(holes))
            for ref, holes in with_holes
        ],
        total_missing_sessions=sum(len(holes) for _, holes in with_holes),
        expected_session_bars=sum(n for _, n, _ in coverage),
        next_scan_in_seconds=next_hole_scan_in_seconds(),
        heals_per_scan=MAX_HOLE_HEALS_PER_SCAN,
        scan_window_days=HOLE_SCAN_WINDOW_DAYS,
    )



def _is_orphan_conditions():
    """SQL conditions for "this Asset row is referenced by nothing"."""
    in_group = select(group_assets.c.asset_id).where(
        group_assets.c.asset_id == Asset.id
    ).exists()
    in_thesis = select(thesis_assets.c.asset_id).where(
        thesis_assets.c.asset_id == Asset.id
    ).exists()
    in_pseudo_etf = select(pseudo_etf_constituents.c.asset_id).where(
        pseudo_etf_constituents.c.asset_id == Asset.id
    ).exists()
    return ~in_group, ~in_thesis, ~in_pseudo_etf


async def list_orphans(db: AsyncSession) -> list[OrphanAsset]:
    """Asset rows referenced by nothing, with what deleting them would cost."""
    rows = (
        await db.execute(
            select(
                Asset.id, Asset.symbol, Asset.name, Asset.type,
                func.count(PriceHistory.id), func.max(PriceHistory.date),
            )
            .outerjoin(PriceHistory, PriceHistory.asset_id == Asset.id)
            .where(*_is_orphan_conditions())
            .group_by(Asset.id)
            .order_by(Asset.symbol)
        )
    ).all()
    return [
        OrphanAsset(
            id=aid, symbol=sym, name=name, type=typ,
            price_bars=bars, latest_bar=latest,
        )
        for aid, sym, name, typ, bars, latest in rows
    ]


async def delete_orphan(db: AsyncSession, asset_id: int) -> None:
    """Hard-delete an orphaned asset row (cascades its price history).

    Refuses anything still referenced — the regular soft delete is the path
    for those; this endpoint can only remove rows nothing depends on.
    """
    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    still_orphan = (
        await db.execute(
            select(Asset.id).where(Asset.id == asset_id, *_is_orphan_conditions())
        )
    ).scalar_one_or_none()
    if still_orphan is None:
        raise HTTPException(
            409, "Asset is referenced by a group, thesis, or pseudo-ETF — not an orphan"
        )
    await db.delete(asset)
    await db.commit()

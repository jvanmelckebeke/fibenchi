"""Collection stats + data-health assembly for the stats page."""

from collections import Counter

from fastapi import HTTPException
from sqlalchemy import func, select
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
    Note,
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
from app.utils import TTLCache

# Both stats endpoints are full scans: `collect_stats` counts every price and
# intraday row, `collect_data_health` loads a 120-day window for every grouped
# asset. Neither reads anything that moves faster than the daily sync and the
# heal scan, so an open stats page re-running them on each poll is pure waste.
# The one visibly live field is data-health's `next_scan_in_seconds`, already
# documented as approximate — a minute of drift is within what it promises.
#
# Known drift: adopting an orphan into a group or thesis goes through the group
# and thesis routers, which know nothing about this cache, so the collection
# counts can lag that by up to the TTL while the (uncached) orphan list updates
# at once. Deletion invalidates because it happens right here; wiring the
# adoption paths in would mean coupling them to stats, which isn't worth it for
# a number that is stale by a minute at most.
_STATS_TTL_SECONDS = 60
_stats_cache = TTLCache(default_ttl=_STATS_TTL_SECONDS, max_size=4)


def reset_stats_cache() -> None:
    """Drop cached stats. For tests, and for anything that mutates the
    collection and wants the next read to reflect it."""
    _stats_cache.clear()


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
    """Collection-size numbers: how much data the instance has accumulated.

    Cached for `_STATS_TTL_SECONDS`; see the cache comment above.
    """
    cached = _stats_cache.get_value("stats")
    if cached is not None:
        return cached

    # Mix buckets cover tracked assets only (in ≥1 group) so the breakdown
    # bar sums to the "tracked" headline it sits under — orphans and
    # thesis-kept rows are reported separately, not mixed in.
    tracked_rows = (
        await db.execute(
            select(Asset.symbol, Asset.type)
            .join(group_assets, group_assets.c.asset_id == Asset.id)
            .distinct()
        )
    ).all()
    mix = Counter(_mix_bucket(sym, typ) for sym, typ in tracked_rows)
    tracked = len(tracked_rows)

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

    stats = StatsResponse(
        assets_total=await _count(db, Asset),
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
    _stats_cache.set_value("stats", stats)
    return stats


async def collect_data_health(db: AsyncSession) -> DataHealthResponse:
    """Session-coverage quality + self-heal status, from the same scan the
    heal itself uses.

    Cached for `_STATS_TTL_SECONDS`; see the cache comment above.
    """
    cached = _stats_cache.get_value("data_health")
    if cached is not None:
        return cached

    coverage = await scan_session_coverage(db)
    with_holes = [(ref, holes) for ref, _, holes in coverage if holes]
    with_holes.sort(key=lambda c: max(c[1]), reverse=True)
    health = DataHealthResponse(
        hole_symbols=[
            HoleSymbol(symbol=ref, missing_sessions=sorted(holes))
            for ref, holes in with_holes
        ],
        total_missing_sessions=sum(len(holes) for _, holes in with_holes),
        expected_session_bars=sum(n for _, n, _ in coverage),
        covered_symbols=len(coverage),
        next_scan_in_seconds=next_hole_scan_in_seconds(),
        heals_per_scan=MAX_HOLE_HEALS_PER_SCAN,
        scan_window_days=HOLE_SCAN_WINDOW_DAYS,
    )
    _stats_cache.set_value("data_health", health)
    return health


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
    """Asset rows referenced by nothing, with what deleting them would cost.

    The cost is two kinds. Price bars are re-fetchable; the note and
    annotations are not, and being orphaned says nothing about whether they
    exist — the soft delete only drops group membership. Counted as correlated
    scalars rather than more joins, which would fan out and multiply the bar
    count by the annotation count.
    """
    annotation_count = (
        select(func.count(Annotation.id))
        .where(Annotation.asset_id == Asset.id)
        .scalar_subquery()
    )
    note_exists = select(Note.id).where(Note.asset_id == Asset.id).exists()
    rows = (
        await db.execute(
            select(
                Asset.id, Asset.symbol, Asset.name, Asset.type,
                func.count(PriceHistory.id), func.max(PriceHistory.date),
                annotation_count, note_exists,
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
            annotations=notes, has_note=has_note,
        )
        for aid, sym, name, typ, bars, latest, notes, has_note in rows
    ]


async def delete_orphan(db: AsyncSession, asset_id: int) -> None:
    """Hard-delete an orphaned asset row (cascades its price history).

    Refuses anything still held by a *container* — group, thesis, pseudo-ETF —
    the regular soft delete being the path for those. It does **not** refuse an
    asset carrying a note or annotations: those cascade away with the row.
    `list_orphans` reports them so the caller can say so before asking.
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
    # The card that triggered this sits next to the cached collection counts;
    # leaving them stale would show the row gone and the total unchanged.
    reset_stats_cache()

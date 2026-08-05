"""Operational endpoints: collection stats and data-health / self-heal status."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.system import DataHealthResponse, OrphanAsset, StatsResponse
from app.services.stats_service import (
    collect_data_health,
    collect_stats,
    delete_orphan,
    list_orphans,
)

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get(
    "/data-health",
    summary="Price-history health and self-heal status",
    response_model=DataHealthResponse,
)
async def get_data_health(db: AsyncSession = Depends(get_db)):
    """Report symbols whose stored history is missing trading sessions
    (typically blanking their σ-Move) and when the background self-heal
    will next attempt repairs.
    """
    return await collect_data_health(db)


@router.get(
    "/stats",
    summary="Collection statistics",
    response_model=StatsResponse,
)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """How much data this instance has accumulated: assets, bars, span,
    groups, theses, and friends.
    """
    return await collect_stats(db)


@router.get(
    "/orphans",
    summary="Orphaned asset rows",
    response_model=list[OrphanAsset],
)
async def get_orphans(db: AsyncSession = Depends(get_db)):
    """Asset rows referenced by nothing — no group, thesis, or pseudo-ETF.
    Candidates for hard deletion or re-adoption into a group/thesis.
    """
    return await list_orphans(db)


@router.delete(
    "/orphans/{asset_id}",
    status_code=204,
    summary="Hard-delete an orphaned asset row",
)
async def remove_orphan(asset_id: int, db: AsyncSession = Depends(get_db)):
    """Delete the asset row and its stored price history. Refused (409) when
    the asset is still referenced by a group, thesis, or pseudo-ETF.
    """
    await delete_orphan(db, asset_id)

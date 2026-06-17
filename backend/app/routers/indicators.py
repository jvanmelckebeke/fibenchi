from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.price import IndicatorSnapshotBase
from app.services.compute.group import compute_indicators_for_symbols

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


@router.get(
    "",
    response_model=dict[str, IndicatorSnapshotBase],
    summary="Batch indicators for arbitrary tracked symbols",
)
async def batch_indicators(
    symbols: list[str] = Query(default=[], description="Tracked ticker symbols"),
    db: AsyncSession = Depends(get_db),
):
    """Latest indicator snapshot per symbol, keyed by symbol.

    DB-backed and addressable by symbol set (not by group) — lets the By-thesis
    view fill indicator columns for members that live in other groups. Untracked
    symbols are omitted from the response.
    """
    return await compute_indicators_for_symbols(db, symbols)

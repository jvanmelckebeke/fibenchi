from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import PeriodType
from app.database import get_db
from app.schemas.price import SparklinePointResponse
from app.services.compute.group import get_sparklines_for_symbols

router = APIRouter(prefix="/api/sparklines", tags=["sparklines"])


@router.get(
    "",
    response_model=dict[str, list[SparklinePointResponse]],
    summary="Batch close prices for arbitrary tracked symbols",
)
async def batch_sparklines(
    symbols: list[str] = Query(default=[], description="Tracked ticker symbols"),
    period: PeriodType = Query("3mo"),
    db: AsyncSession = Depends(get_db),
):
    """Close-price series per symbol, keyed by symbol.

    The symbol-addressed sibling of ``/api/groups/{id}/sparklines``, matching
    ``/api/indicators``. A caller holding a roster that spans groups makes one
    request instead of one per group, and symbols with several memberships come
    back once. Untracked symbols are omitted from the response.
    """
    return await get_sparklines_for_symbols(db, symbols, period)

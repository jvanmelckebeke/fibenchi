"""Market schedule endpoints — venue phases from the trading calendars."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.market import CalendarPhase
from app.services.market_phase_service import collect_market_phases

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get(
    "/phases",
    summary="Scheduled phase per in-use venue calendar",
    response_model=dict[str, CalendarPhase],
)
async def get_market_phases(db: AsyncSession = Depends(get_db)):
    """Deterministic, calendar-derived phase (and next transition) for every
    venue calendar used by grouped assets. Works even when the quote feed is
    degraded; the SSE stream's live market_state should win when present.
    """
    return await collect_market_phases(db)

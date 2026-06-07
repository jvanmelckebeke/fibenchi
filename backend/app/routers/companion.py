from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.companion import CompanionConfig
from app.services import companion_service

router = APIRouter(prefix="/api/companion", tags=["companion"])


@router.get("/config", response_model=CompanionConfig, summary="Companion app config bundle")
async def get_companion_config(db: AsyncSession = Depends(get_db)):
    """Versioned config bundle (groups + tickers + tags) for the mobile companion.

    The companion fetches live market data directly from Yahoo on-device; this
    endpoint only tells it *what to track*.
    """
    return await companion_service.build_config(db)

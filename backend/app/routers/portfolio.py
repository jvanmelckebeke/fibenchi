from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import PeriodType
from app.database import get_db
from app.schemas.portfolio import AssetPerformance, PortfolioIndexResponse
from app.services.compute.portfolio import compute_performers, compute_portfolio_index

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/index", response_model=PortfolioIndexResponse, summary="Get composite portfolio index")
async def get_portfolio_index(period: PeriodType = Query("1y"), db: AsyncSession = Depends(get_db)):
    """Compute equal-weight composite index of all grouped assets."""
    return await compute_portfolio_index(db, period)


@router.get("/performers", response_model=list[AssetPerformance], summary="Get top and bottom performers by return")
async def get_performers(period: PeriodType = Query("1y"), db: AsyncSession = Depends(get_db)):
    """Return grouped assets ranked by period return (best first)."""
    return await compute_performers(db, period)

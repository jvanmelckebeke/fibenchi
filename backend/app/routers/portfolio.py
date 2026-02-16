from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.portfolio import compute_performers, compute_portfolio_index

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class PortfolioIndexResponse(BaseModel):
    dates: list[date]
    values: list[float]
    current: float
    change: float
    change_pct: float


class AssetPerformance(BaseModel):
    symbol: str
    name: str
    type: str
    change_pct: float


@router.get("/index", response_model=PortfolioIndexResponse, summary="Get composite portfolio index")
async def get_portfolio_index(period: str = "1y", db: AsyncSession = Depends(get_db)):
    """Compute equal-weight composite index of all watchlisted assets."""
    return await compute_portfolio_index(db, period)


@router.get("/performers", response_model=list[AssetPerformance], summary="Get top and bottom performers by return")
async def get_performers(period: str = "1y", db: AsyncSession = Depends(get_db)):
    """Return watchlisted assets ranked by period return (best first)."""
    return await compute_performers(db, period)

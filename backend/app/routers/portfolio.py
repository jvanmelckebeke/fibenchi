from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Asset
from app.services.pseudo_etf import calculate_performance

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

_PERIOD_DAYS = {
    "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825,
}


class PortfolioIndexResponse(BaseModel):
    dates: list[date]
    values: list[float]
    current: float
    change: float
    change_pct: float


@router.get("/index", response_model=PortfolioIndexResponse)
async def get_portfolio_index(period: str = "1y", db: AsyncSession = Depends(get_db)):
    """Compute equal-weight composite index of all watchlisted assets."""
    days = _PERIOD_DAYS.get(period, 365)
    start_date = date.today() - timedelta(days=days)

    result = await db.execute(
        select(Asset.id).where(Asset.watchlisted == True)  # noqa: E712
    )
    asset_ids = list(result.scalars().all())

    if not asset_ids:
        return PortfolioIndexResponse(
            dates=[], values=[], current=0, change=0, change_pct=0,
        )

    points = await calculate_performance(db, asset_ids, start_date, base_value=1000.0)

    if not points:
        return PortfolioIndexResponse(
            dates=[], values=[], current=0, change=0, change_pct=0,
        )

    dates = [p["date"] for p in points]
    values = [p["value"] for p in points]
    current = values[-1]
    first = values[0]
    change = current - first
    change_pct = (change / first) * 100 if first != 0 else 0

    return PortfolioIndexResponse(
        dates=dates,
        values=values,
        current=round(current, 2),
        change=round(change, 2),
        change_pct=round(change_pct, 2),
    )

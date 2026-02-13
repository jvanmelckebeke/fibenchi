from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Asset, PriceHistory
from app.services.pseudo_etf import calculate_performance

# Minimum stock price before an asset is included in the composite index.
# Prevents low-IPO-price stocks from distorting equal-weight returns.
_MIN_ENTRY_PRICE = 10.0

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


class AssetPerformance(BaseModel):
    symbol: str
    name: str
    type: str
    change_pct: float


async def _get_watchlisted_ids(db: AsyncSession) -> list[int]:
    result = await db.execute(
        select(Asset.id).where(Asset.watchlisted == True)  # noqa: E712
    )
    return list(result.scalars().all())


@router.get("/index", response_model=PortfolioIndexResponse, summary="Get composite portfolio index")
async def get_portfolio_index(period: str = "1y", db: AsyncSession = Depends(get_db)):
    """Compute equal-weight composite index of all watchlisted assets."""
    days = _PERIOD_DAYS.get(period, 365)
    start_date = date.today() - timedelta(days=days)

    asset_ids = await _get_watchlisted_ids(db)

    if not asset_ids:
        return PortfolioIndexResponse(
            dates=[], values=[], current=0, change=0, change_pct=0,
        )

    points = await calculate_performance(
        db, asset_ids, start_date, base_value=1000.0,
        dynamic_entry=True, min_entry_price=_MIN_ENTRY_PRICE,
    )

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


@router.get("/performers", response_model=list[AssetPerformance], summary="Get top and bottom performers by return")
async def get_performers(period: str = "1y", db: AsyncSession = Depends(get_db)):
    """Return watchlisted assets ranked by period return (best first)."""
    days = _PERIOD_DAYS.get(period, 365)
    start_date = date.today() - timedelta(days=days)

    result = await db.execute(
        select(Asset).where(Asset.watchlisted == True)  # noqa: E712
    )
    assets = result.scalars().all()

    if not assets:
        return []

    asset_map = {a.id: a for a in assets}
    asset_ids = list(asset_map.keys())

    # Get earliest price on or after start_date per asset
    first_prices_q = await db.execute(
        select(
            PriceHistory.asset_id,
            func.min(PriceHistory.date).label("first_date"),
        )
        .where(PriceHistory.asset_id.in_(asset_ids))
        .where(PriceHistory.date >= start_date)
        .group_by(PriceHistory.asset_id)
    )
    first_dates = {row.asset_id: row.first_date for row in first_prices_q}

    # Get latest price per asset
    last_prices_q = await db.execute(
        select(
            PriceHistory.asset_id,
            func.max(PriceHistory.date).label("last_date"),
        )
        .where(PriceHistory.asset_id.in_(asset_ids))
        .group_by(PriceHistory.asset_id)
    )
    last_dates = {row.asset_id: row.last_date for row in last_prices_q}

    # Fetch the actual close prices for those dates
    date_pairs = []
    for aid in asset_ids:
        if aid in first_dates:
            date_pairs.append((aid, first_dates[aid]))
        if aid in last_dates:
            date_pairs.append((aid, last_dates[aid]))

    if not date_pairs:
        return []

    prices_q = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.asset_id.in_(asset_ids))
        .where(
            PriceHistory.date.in_(
                list({d for _, d in date_pairs})
            )
        )
    )
    price_rows = prices_q.scalars().all()

    # Build lookup: (asset_id, date) -> close
    price_map: dict[tuple[int, date], float] = {}
    for p in price_rows:
        price_map[(p.asset_id, p.date)] = float(p.close)

    performers = []
    for aid, asset in asset_map.items():
        first_d = first_dates.get(aid)
        last_d = last_dates.get(aid)
        if not first_d or not last_d or first_d == last_d:
            continue
        first_close = price_map.get((aid, first_d))
        last_close = price_map.get((aid, last_d))
        if first_close and last_close and first_close > 0:
            pct = ((last_close - first_close) / first_close) * 100
            performers.append(AssetPerformance(
                symbol=asset.symbol,
                name=asset.name,
                type=asset.type.value,
                change_pct=round(pct, 2),
            ))

    performers.sort(key=lambda p: p.change_pct, reverse=True)
    return performers

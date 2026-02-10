from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Asset, PriceHistory
from app.schemas.price import IndicatorResponse, PriceResponse
from app.services.indicators import compute_indicators
from app.services.price_sync import sync_asset_prices, sync_asset_prices_range

import pandas as pd

router = APIRouter(prefix="/api/assets/{symbol}", tags=["prices"])

# Calendar days for each period string
_PERIOD_DAYS = {
    "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825,
}
# Extra calendar days to fetch for indicator warmup (~50 trading days for SMA50)
_WARMUP_DAYS = 80


def _display_start(period: str) -> date:
    """Return the earliest date to include in the response for a given period."""
    days = _PERIOD_DAYS.get(period, 90)
    return date.today() - timedelta(days=days)


async def _get_asset(symbol: str, db: AsyncSession) -> Asset:
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")
    return asset


async def _ensure_prices(db: AsyncSession, asset: Asset, period: str) -> list[PriceHistory]:
    """Load all prices from DB, fetching from Yahoo if the requested period isn't covered."""
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset.id)
        .order_by(PriceHistory.date)
    )
    prices = result.scalars().all()

    needed_start = _display_start(period)

    if not prices:
        count = await sync_asset_prices(db, asset, period=period)
        if count == 0:
            raise HTTPException(404, f"No price data available for {asset.symbol}")
    elif prices[0].date > needed_start:
        # DB has data but doesn't go back far enough for the requested period
        await sync_asset_prices_range(db, asset, needed_start, date.today())

    if not prices or prices[0].date > needed_start:
        result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.asset_id == asset.id)
            .order_by(PriceHistory.date)
        )
        prices = result.scalars().all()

    return prices


@router.get("/prices", response_model=list[PriceResponse])
async def get_prices(symbol: str, period: str = "3mo", db: AsyncSession = Depends(get_db)):
    asset = await _get_asset(symbol, db)
    prices = await _ensure_prices(db, asset, period)
    start = _display_start(period)
    return [p for p in prices if p.date >= start]


@router.get("/indicators", response_model=list[IndicatorResponse])
async def get_indicators(symbol: str, period: str = "3mo", db: AsyncSession = Depends(get_db)):
    asset = await _get_asset(symbol, db)
    prices = await _ensure_prices(db, asset, period)

    start = _display_start(period)
    warmup_start = start - timedelta(days=_WARMUP_DAYS)

    # If DB doesn't have enough warmup data, fetch extra from Yahoo
    if prices and prices[0].date > warmup_start:
        await sync_asset_prices_range(db, asset, warmup_start, date.today())
        result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.asset_id == asset.id)
            .order_by(PriceHistory.date)
        )
        prices = result.scalars().all()

    # Build DataFrame from ALL available data for indicator computation
    df = pd.DataFrame([{
        "date": p.date,
        "open": float(p.open),
        "high": float(p.high),
        "low": float(p.low),
        "close": float(p.close),
        "volume": p.volume,
    } for p in prices]).set_index("date")

    indicators = compute_indicators(df)

    # Only return rows within the display period
    rows = []
    for dt, row in indicators.iterrows():
        if dt < start:
            continue
        rows.append(IndicatorResponse(
            date=dt,
            close=round(row["close"], 4),
            rsi=round(row["rsi"], 2) if pd.notna(row["rsi"]) else None,
            sma_20=round(row["sma_20"], 4) if pd.notna(row["sma_20"]) else None,
            sma_50=round(row["sma_50"], 4) if pd.notna(row["sma_50"]) else None,
            bb_upper=round(row["bb_upper"], 4) if pd.notna(row["bb_upper"]) else None,
            bb_middle=round(row["bb_middle"], 4) if pd.notna(row["bb_middle"]) else None,
            bb_lower=round(row["bb_lower"], 4) if pd.notna(row["bb_lower"]) else None,
            macd=round(row["macd"], 4) if pd.notna(row["macd"]) else None,
            macd_signal=round(row["macd_signal"], 4) if pd.notna(row["macd_signal"]) else None,
            macd_hist=round(row["macd_hist"], 4) if pd.notna(row["macd_hist"]) else None,
        ))

    return rows


@router.post("/refresh", status_code=200)
async def refresh_prices(symbol: str, period: str = "3mo", db: AsyncSession = Depends(get_db)):
    asset = await _get_asset(symbol, db)
    count = await sync_asset_prices(db, asset, period=period)
    return {"symbol": asset.symbol, "synced": count}

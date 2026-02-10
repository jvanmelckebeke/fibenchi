from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Asset, PriceHistory
from app.schemas.price import IndicatorResponse, PriceResponse
from app.services.indicators import compute_indicators
from app.services.price_sync import sync_asset_prices

import pandas as pd

router = APIRouter(prefix="/api/assets/{symbol}", tags=["prices"])


async def _get_asset(symbol: str, db: AsyncSession) -> Asset:
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")
    return asset


@router.get("/prices", response_model=list[PriceResponse])
async def get_prices(symbol: str, period: str = "3mo", db: AsyncSession = Depends(get_db)):
    asset = await _get_asset(symbol, db)

    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset.id)
        .order_by(PriceHistory.date)
    )
    prices = result.scalars().all()

    if not prices:
        count = await sync_asset_prices(db, asset, period=period)
        if count == 0:
            raise HTTPException(404, f"No price data available for {symbol}")
        result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.asset_id == asset.id)
            .order_by(PriceHistory.date)
        )
        prices = result.scalars().all()

    return prices


@router.get("/indicators", response_model=list[IndicatorResponse])
async def get_indicators(symbol: str, period: str = "3mo", db: AsyncSession = Depends(get_db)):
    asset = await _get_asset(symbol, db)

    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset.id)
        .order_by(PriceHistory.date)
    )
    prices = result.scalars().all()

    if not prices:
        count = await sync_asset_prices(db, asset, period=period)
        if count == 0:
            raise HTTPException(404, f"No price data available for {symbol}")
        result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.asset_id == asset.id)
            .order_by(PriceHistory.date)
        )
        prices = result.scalars().all()

    df = pd.DataFrame([{
        "date": p.date,
        "open": float(p.open),
        "high": float(p.high),
        "low": float(p.low),
        "close": float(p.close),
        "volume": p.volume,
    } for p in prices]).set_index("date")

    indicators = compute_indicators(df)

    rows = []
    for dt, row in indicators.iterrows():
        rows.append(IndicatorResponse(
            date=dt,
            close=round(row["close"], 4),
            rsi=round(row["rsi"], 2) if pd.notna(row["rsi"]) else None,
            sma_20=round(row["sma_20"], 4) if pd.notna(row["sma_20"]) else None,
            sma_50=round(row["sma_50"], 4) if pd.notna(row["sma_50"]) else None,
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

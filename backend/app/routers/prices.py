from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import PERIOD_DAYS, WARMUP_DAYS
from app.database import get_db
from app.models import Asset, PriceHistory
from app.routers.deps import find_asset, get_asset
from app.schemas.price import IndicatorResponse, PriceResponse
from app.services.indicators import compute_indicators, safe_round
from app.services.price_sync import sync_asset_prices, sync_asset_prices_range
from app.services.yahoo import fetch_history

import pandas as pd

router = APIRouter(prefix="/api/assets/{symbol}", tags=["prices"])


def _display_start(period: str) -> date:
    """Return the earliest date to include in the response for a given period."""
    days = PERIOD_DAYS.get(period, 90)
    return date.today() - timedelta(days=days)


def _fetch_ephemeral(symbol: str, period: str, warmup: bool = False) -> pd.DataFrame:
    """Fetch price data from Yahoo without persisting to DB.

    Used for non-watchlisted symbols viewed via ETF holdings links.
    """
    days = PERIOD_DAYS.get(period, 90)
    if warmup:
        days += WARMUP_DAYS
    start_date = date.today() - timedelta(days=days)
    try:
        df = fetch_history(symbol.upper(), start=start_date, end=date.today())
    except (ValueError, Exception):
        raise HTTPException(404, f"No price data available for {symbol}")

    if df.empty:
        raise HTTPException(404, f"No price data available for {symbol}")

    # Normalise index to date objects
    if hasattr(df.index, "date"):
        df.index = df.index.date

    return df


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


@router.get("/prices", response_model=list[PriceResponse], summary="Get OHLCV price history")
async def get_prices(symbol: str, period: str = "3mo", db: AsyncSession = Depends(get_db)):
    """Return daily OHLCV price history for a symbol.

    For watchlisted assets, prices are read from the database (and auto-synced
    from Yahoo Finance if the requested period isn't yet covered). For
    non-watchlisted symbols, prices are fetched ephemerally from Yahoo without
    persisting.

    Supported periods: `1mo`, `3mo` (default), `6mo`, `1y`, `2y`, `5y`.
    """
    asset = await find_asset(symbol, db)

    if asset:
        prices = await _ensure_prices(db, asset, period)
        start = _display_start(period)
        return [p for p in prices if p.date >= start]

    # Ephemeral: fetch directly from Yahoo, no DB persistence
    df = _fetch_ephemeral(symbol, period)
    start = _display_start(period)
    rows = []
    for dt, row in df.iterrows():
        if dt < start:
            continue
        rows.append(PriceResponse(
            date=dt,
            open=round(float(row["open"]), 4),
            high=round(float(row["high"]), 4),
            low=round(float(row["low"]), 4),
            close=round(float(row["close"]), 4),
            volume=int(row["volume"]),
        ))
    return rows


@router.get("/indicators", response_model=list[IndicatorResponse], summary="Get technical indicators (RSI, SMA, MACD, Bollinger)")
async def get_indicators(symbol: str, period: str = "3mo", db: AsyncSession = Depends(get_db)):
    """Return daily indicator time series for a symbol.

    Includes RSI (14), SMA 20/50, Bollinger Bands (20, 2σ), and MACD (12/26/9).
    An extra 80-day warmup window is fetched internally so that the first
    returned data point already has converged indicator values.

    Supported periods: `1mo`, `3mo` (default), `6mo`, `1y`, `2y`, `5y`.
    """
    asset = await find_asset(symbol, db)
    start = _display_start(period)

    if asset:
        prices = await _ensure_prices(db, asset, period)
        warmup_start = start - timedelta(days=WARMUP_DAYS)

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
    else:
        # Ephemeral: fetch with warmup directly from Yahoo
        df = _fetch_ephemeral(symbol, period, warmup=True)

    indicators = compute_indicators(df)

    # Only return rows within the display period
    rows = []
    for dt, row in indicators.iterrows():
        if dt < start:
            continue
        rows.append(IndicatorResponse(
            date=dt,
            close=round(row["close"], 4),
            rsi=safe_round(row["rsi"], 2),
            sma_20=safe_round(row["sma_20"], 4),
            sma_50=safe_round(row["sma_50"], 4),
            bb_upper=safe_round(row["bb_upper"], 4),
            bb_middle=safe_round(row["bb_middle"], 4),
            bb_lower=safe_round(row["bb_lower"], 4),
            macd=safe_round(row["macd"], 4),
            macd_signal=safe_round(row["macd_signal"], 4),
            macd_hist=safe_round(row["macd_hist"], 4),
        ))

    return rows


@router.post("/refresh", status_code=200, summary="Force-refresh prices from Yahoo Finance")
async def refresh_prices(symbol: str, period: str = "3mo", db: AsyncSession = Depends(get_db)):
    """Force a re-sync of price data from Yahoo Finance for a watchlisted asset.

    Returns the number of price points upserted.
    """
    asset = await get_asset(symbol, db)
    count = await sync_asset_prices(db, asset, period=period)
    return {"symbol": asset.symbol, "synced": count}

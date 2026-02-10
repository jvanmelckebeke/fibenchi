from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pandas as pd

from app.database import get_db
from app.models import Asset
from app.schemas.price import EtfHoldingsResponse, HoldingIndicatorResponse
from app.services.indicators import compute_indicators
from app.services.yahoo import batch_fetch_history, fetch_etf_holdings

router = APIRouter(prefix="/api/assets/{symbol}/holdings", tags=["holdings"])


async def _get_asset(symbol: str, db: AsyncSession) -> Asset:
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")
    return asset


def _bb_position(close: float, upper: float, middle: float, lower: float) -> str:
    """Classify where price sits relative to Bollinger Bands."""
    if close > upper:
        return "above"
    elif close > middle:
        return "upper"
    elif close > lower:
        return "lower"
    else:
        return "below"


@router.get("", response_model=EtfHoldingsResponse)
async def get_holdings(symbol: str, db: AsyncSession = Depends(get_db)):
    asset = await _get_asset(symbol, db)
    if asset.type.value != "etf":
        raise HTTPException(400, f"{symbol} is not an ETF")
    data = fetch_etf_holdings(symbol)
    if not data:
        raise HTTPException(404, f"No holdings data for {symbol}")
    return data


@router.get("/indicators", response_model=list[HoldingIndicatorResponse])
async def get_holdings_indicators(symbol: str, db: AsyncSession = Depends(get_db)):
    """Return latest indicator snapshot for each of the ETF's top holdings."""
    asset = await _get_asset(symbol, db)
    if asset.type.value != "etf":
        raise HTTPException(400, f"{symbol} is not an ETF")

    data = fetch_etf_holdings(symbol)
    if not data:
        raise HTTPException(404, f"No holdings data for {symbol}")

    holding_symbols = [h["symbol"] for h in data["top_holdings"] if h["symbol"]]
    if not holding_symbols:
        return []

    # Batch fetch ~3 months of history (enough for SMA50 warmup)
    histories = batch_fetch_history(holding_symbols, period="3mo")

    results = []
    for sym in holding_symbols:
        df = histories.get(sym)
        if df is None or df.empty or len(df) < 2:
            results.append(HoldingIndicatorResponse(symbol=sym))
            continue

        indicators = compute_indicators(df)
        latest = indicators.iloc[-1]
        prev_close = indicators.iloc[-2]["close"] if len(indicators) >= 2 else None

        change_pct = None
        if prev_close and prev_close != 0:
            change_pct = round((latest["close"] - prev_close) / prev_close * 100, 2)

        macd_dir = None
        if pd.notna(latest["macd"]) and pd.notna(latest["macd_signal"]):
            macd_dir = "bullish" if latest["macd"] > latest["macd_signal"] else "bearish"

        bb_pos = None
        if pd.notna(latest["bb_upper"]) and pd.notna(latest["bb_middle"]) and pd.notna(latest["bb_lower"]):
            bb_pos = _bb_position(latest["close"], latest["bb_upper"], latest["bb_middle"], latest["bb_lower"])

        results.append(HoldingIndicatorResponse(
            symbol=sym,
            close=round(latest["close"], 2),
            change_pct=change_pct,
            rsi=round(latest["rsi"], 2) if pd.notna(latest["rsi"]) else None,
            sma_20=round(latest["sma_20"], 2) if pd.notna(latest["sma_20"]) else None,
            sma_50=round(latest["sma_50"], 2) if pd.notna(latest["sma_50"]) else None,
            macd_signal_dir=macd_dir,
            bb_position=bb_pos,
        ))

    return results

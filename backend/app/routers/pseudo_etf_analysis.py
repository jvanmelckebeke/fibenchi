from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import pandas as pd

from app.database import get_db
from app.models.pseudo_etf import PseudoETF
from app.schemas.pseudo_etf import PerformanceBreakdownPoint, ConstituentIndicatorResponse
from app.services.pseudo_etf import calculate_performance
from app.services.indicators import compute_indicators
from app.services.yahoo import batch_fetch_currencies, batch_fetch_history

router = APIRouter(prefix="/api/pseudo-etfs", tags=["pseudo-etfs"])


def _bb_position(close: float, upper: float, middle: float, lower: float) -> str:
    if close > upper:
        return "above"
    elif close > middle:
        return "upper"
    elif close > lower:
        return "lower"
    else:
        return "below"


@router.get("/{etf_id}/performance", response_model=list[PerformanceBreakdownPoint], summary="Get indexed performance with per-constituent breakdown")
async def get_performance(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    asset_ids = [a.id for a in etf.constituents]
    if not asset_ids:
        return []

    return await calculate_performance(
        db, asset_ids, etf.base_date, float(etf.base_value), include_breakdown=True
    )


@router.get("/{etf_id}/constituents/indicators", response_model=list[ConstituentIndicatorResponse], summary="Get technical indicators for each constituent")
async def get_constituent_indicators(etf_id: int, db: AsyncSession = Depends(get_db)):
    """Return latest indicator snapshot for each constituent of a pseudo-ETF."""
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    if not etf.constituents:
        return []

    # Get latest performance breakdown for weight calculation
    asset_ids = [a.id for a in etf.constituents]
    perf = await calculate_performance(
        db, asset_ids, etf.base_date, float(etf.base_value), include_breakdown=True
    )
    weight_map: dict[str, float] = {}
    if perf:
        last_point = perf[-1]
        breakdown = last_point.get("breakdown", {})
        total = last_point["value"]
        if total > 0:
            weight_map = {sym: round(val / total * 100, 2) for sym, val in breakdown.items()}

    symbols = [a.symbol for a in etf.constituents]
    symbol_to_name = {a.symbol: a.name for a in etf.constituents}

    histories = batch_fetch_history(symbols, period="3mo")
    currencies = batch_fetch_currencies(symbols)

    results = []
    for sym in symbols:
        currency = currencies.get(sym, "USD")
        df = histories.get(sym)
        if df is None or df.empty or len(df) < 2:
            results.append(ConstituentIndicatorResponse(
                symbol=sym,
                name=symbol_to_name.get(sym),
                currency=currency,
                weight_pct=weight_map.get(sym),
            ))
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

        results.append(ConstituentIndicatorResponse(
            symbol=sym,
            name=symbol_to_name.get(sym),
            currency=currency,
            weight_pct=weight_map.get(sym),
            close=round(latest["close"], 2),
            change_pct=change_pct,
            rsi=round(latest["rsi"], 2) if pd.notna(latest["rsi"]) else None,
            sma_20=round(latest["sma_20"], 2) if pd.notna(latest["sma_20"]) else None,
            sma_50=round(latest["sma_50"], 2) if pd.notna(latest["sma_50"]) else None,
            macd=round(latest["macd"], 4) if pd.notna(latest["macd"]) else None,
            macd_signal=round(latest["macd_signal"], 4) if pd.notna(latest["macd_signal"]) else None,
            macd_hist=round(latest["macd_hist"], 4) if pd.notna(latest["macd_hist"]) else None,
            macd_signal_dir=macd_dir,
            bb_upper=round(latest["bb_upper"], 2) if pd.notna(latest["bb_upper"]) else None,
            bb_middle=round(latest["bb_middle"], 2) if pd.notna(latest["bb_middle"]) else None,
            bb_lower=round(latest["bb_lower"], 2) if pd.notna(latest["bb_lower"]) else None,
            bb_position=bb_pos,
        ))

    return results

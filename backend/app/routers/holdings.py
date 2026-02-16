from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.deps import get_asset
from app.schemas.price import EtfHoldingsResponse, HoldingIndicatorResponse
from app.services.indicators import compute_indicators, build_indicator_snapshot
from app.services.yahoo import batch_fetch_currencies, batch_fetch_history, fetch_etf_holdings

router = APIRouter(prefix="/api/assets/{symbol}/holdings", tags=["holdings"])


@router.get("", response_model=EtfHoldingsResponse, summary="Get ETF top holdings")
async def get_holdings(symbol: str, db: AsyncSession = Depends(get_db)):
    """Return the top holdings and sector weightings for an ETF.

    Only available for assets with `type=etf`. Data is fetched live from Yahoo Finance.
    """
    asset = await get_asset(symbol, db)
    if asset.type.value != "etf":
        raise HTTPException(400, f"{symbol} is not an ETF")
    data = fetch_etf_holdings(symbol)
    if not data:
        raise HTTPException(404, f"No holdings data for {symbol}")
    return data


@router.get("/indicators", response_model=list[HoldingIndicatorResponse], summary="Get technical indicators for each ETF holding")
async def get_holdings_indicators(symbol: str, db: AsyncSession = Depends(get_db)):
    """Return latest indicator snapshot for each of the ETF's top holdings."""
    asset = await get_asset(symbol, db)
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
    currencies = batch_fetch_currencies(holding_symbols)

    results = []
    for sym in holding_symbols:
        currency = currencies.get(sym, "USD")
        df = histories.get(sym)
        if df is None or df.empty or len(df) < 2:
            results.append(HoldingIndicatorResponse(symbol=sym, currency=currency))
            continue

        snapshot = build_indicator_snapshot(compute_indicators(df))
        results.append(HoldingIndicatorResponse(symbol=sym, currency=currency, **snapshot))

    return results

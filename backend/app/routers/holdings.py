import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.deps import get_asset
from app.schemas.price import EtfHoldingsResponse, HoldingIndicatorResponse
from app.services.indicators import compute_batch_indicator_snapshots
from app.services.yahoo import fetch_etf_holdings

router = APIRouter(prefix="/api/assets/{symbol}/holdings", tags=["holdings"])


@router.get("", response_model=EtfHoldingsResponse, summary="Get ETF top holdings")
async def get_holdings(symbol: str, db: AsyncSession = Depends(get_db)):
    """Return the top holdings and sector weightings for an ETF.

    Only available for assets with `type=etf`. Data is fetched live from Yahoo Finance.
    """
    asset = await get_asset(symbol, db)
    if asset.type.value != "etf":
        raise HTTPException(400, f"{symbol} is not an ETF")
    data = await asyncio.to_thread(fetch_etf_holdings, symbol)
    if not data:
        raise HTTPException(404, f"No holdings data for {symbol}")
    return data


@router.get("/indicators", response_model=list[HoldingIndicatorResponse], summary="Get technical indicators for each ETF holding")
async def get_holdings_indicators(symbol: str, db: AsyncSession = Depends(get_db)):
    """Return latest indicator snapshot for each of the ETF's top holdings."""
    asset = await get_asset(symbol, db)
    if asset.type.value != "etf":
        raise HTTPException(400, f"{symbol} is not an ETF")

    data = await asyncio.to_thread(fetch_etf_holdings, symbol)
    if not data:
        raise HTTPException(404, f"No holdings data for {symbol}")

    holding_symbols = [h["symbol"] for h in data["top_holdings"] if h["symbol"]]
    if not holding_symbols:
        return []

    snapshots = await asyncio.to_thread(compute_batch_indicator_snapshots, holding_symbols)
    return [HoldingIndicatorResponse(**s) for s in snapshots]

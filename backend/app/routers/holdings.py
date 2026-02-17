from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.price import EtfHoldingsResponse, HoldingIndicatorResponse
from app.services import holdings_service

router = APIRouter(prefix="/api/assets/{symbol}/holdings", tags=["holdings"])


@router.get("", response_model=EtfHoldingsResponse, summary="Get ETF top holdings")
async def get_holdings(symbol: str, db: AsyncSession = Depends(get_db)):
    """Return the top holdings and sector weightings for an ETF.

    Only available for assets with `type=etf`. Data is fetched live from Yahoo Finance.
    """
    return await holdings_service.get_holdings(db, symbol)


@router.get("/indicators", response_model=list[HoldingIndicatorResponse], summary="Get technical indicators for each ETF holding")
async def get_holdings_indicators(symbol: str, db: AsyncSession = Depends(get_db)):
    """Return latest indicator snapshot for each of the ETF's top holdings."""
    snapshots = await holdings_service.get_holdings_indicators(db, symbol)
    return [HoldingIndicatorResponse(**s) for s in snapshots]

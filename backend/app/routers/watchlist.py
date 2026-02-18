"""Batch endpoints for the watchlist page.

These return aggregated data for assets in the default Watchlist group,
eliminating the N+1 pattern of fetching prices/indicators per asset card.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.compute.watchlist import compute_and_cache_indicators, get_batch_sparklines

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("/sparklines", summary="Batch close prices for sparkline charts")
async def batch_sparklines(
    period: str = "3mo",
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[dict]]:
    """Return close-price sparkline data for every asset in the default Watchlist group.

    Response shape: `{symbol: [{date, close}, ...]}`.

    Supported periods: `1mo`, `3mo` (default), `6mo`, `1y`, `2y`, `5y`.
    """
    return await get_batch_sparklines(db, period)


@router.get("/indicators", summary="Batch latest indicator values for watchlist cards")
async def batch_indicators(
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict]:
    """Return the latest RSI and MACD indicator values for every asset in the
    default Watchlist group.

    Response shape: `{symbol: {rsi, macd, macd_signal, macd_hist}}`.
    """
    return await compute_and_cache_indicators(db)

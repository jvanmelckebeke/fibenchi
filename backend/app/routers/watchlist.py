"""Batch endpoints for the watchlist page.

These return aggregated data for all watchlisted assets in a single request,
eliminating the N+1 pattern of fetching prices/indicators per asset card.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import PERIOD_DAYS
from app.database import get_db
from app.models import Asset, PriceHistory
from app.services.watchlist import compute_and_cache_indicators

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("/sparklines", summary="Batch close prices for sparkline charts")
async def batch_sparklines(
    period: str = "3mo",
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[dict]]:
    """Return close-price sparkline data for every watchlisted asset in a single query.

    Response shape: `{symbol: [{date, close}, ...]}`.

    Supported periods: `1mo`, `3mo` (default), `6mo`, `1y`, `2y`, `5y`.

    This endpoint replaces per-card price fetches on the watchlist page.
    """
    days = PERIOD_DAYS.get(period, 90)
    start = date.today() - timedelta(days=days)

    assets_result = await db.execute(
        select(Asset.id, Asset.symbol).where(Asset.watchlisted == True)  # noqa: E712
    )
    asset_rows = assets_result.all()
    if not asset_rows:
        return {}

    asset_ids = [r.id for r in asset_rows]
    id_to_symbol = {r.id: r.symbol for r in asset_rows}

    prices_result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.asset_id.in_(asset_ids),
            PriceHistory.date >= start,
        )
        .order_by(PriceHistory.asset_id, PriceHistory.date)
    )
    prices = prices_result.scalars().all()

    out: dict[str, list[dict]] = {sym: [] for sym in id_to_symbol.values()}
    for p in prices:
        sym = id_to_symbol.get(p.asset_id)
        if sym:
            out[sym].append({"date": p.date.isoformat(), "close": round(float(p.close), 4)})

    return out


@router.get("/indicators", summary="Batch latest indicator values for watchlist cards")
async def batch_indicators(
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict]:
    """Return the latest RSI and MACD indicator values for every watchlisted asset.

    Response shape: `{symbol: {rsi, macd, macd_signal, macd_hist}}`.

    Values are computed from ~3 months of price history with an 80-day warmup
    window for SMA50/Bollinger Band convergence. Only the most recent non-null
    values are returned — this is optimised for the watchlist card badges, not
    for charting full indicator time series.

    Results are cached for 10 minutes, keyed on the set of watchlisted symbols
    and the latest price date. The cache auto-invalidates when new prices are
    synced (the latest date changes).
    """
    return await compute_and_cache_indicators(db)

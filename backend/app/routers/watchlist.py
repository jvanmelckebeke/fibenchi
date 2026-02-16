"""Batch endpoints for the watchlist page.

These return aggregated data for all watchlisted assets in a single request,
eliminating the N+1 pattern of fetching prices/indicators per asset card.
"""

import time
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

import pandas as pd

from app.database import get_db
from app.models import Asset, PriceHistory
from app.services.indicators import compute_indicators

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

# In-memory cache for batch indicator snapshots.
# Key: (frozenset of symbols, latest_price_date) — auto-invalidates when prices change.
_indicator_cache: dict[tuple, tuple[dict, float]] = {}
_INDICATOR_CACHE_TTL = 600  # 10 minutes

_PERIOD_DAYS = {
    "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825,
}
_WARMUP_DAYS = 80


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
    days = _PERIOD_DAYS.get(period, 90)
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
    assets_result = await db.execute(
        select(Asset.id, Asset.symbol).where(Asset.watchlisted == True)  # noqa: E712
    )
    asset_rows = assets_result.all()
    if not asset_rows:
        return {}

    asset_ids = [r.id for r in asset_rows]
    id_to_symbol = {r.id: r.symbol for r in asset_rows}

    # Build cache key: symbols + latest price date
    latest_date_result = await db.execute(
        select(func.max(PriceHistory.date)).where(PriceHistory.asset_id.in_(asset_ids))
    )
    latest_date = latest_date_result.scalar()
    cache_key = (frozenset(id_to_symbol.values()), latest_date)

    cached = _indicator_cache.get(cache_key)
    if cached and time.monotonic() - cached[1] < _INDICATOR_CACHE_TTL:
        return cached[0]

    # Fetch enough history for indicator warmup (SMA50 needs ~50 trading days)
    warmup_start = date.today() - timedelta(days=_PERIOD_DAYS["3mo"] + _WARMUP_DAYS)

    prices_result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.asset_id.in_(asset_ids),
            PriceHistory.date >= warmup_start,
        )
        .order_by(PriceHistory.asset_id, PriceHistory.date)
    )
    all_prices = prices_result.scalars().all()

    # Group prices by asset
    grouped: dict[int, list[PriceHistory]] = {}
    for p in all_prices:
        grouped.setdefault(p.asset_id, []).append(p)

    out: dict[str, dict] = {}
    for asset_id, symbol in id_to_symbol.items():
        prices = grouped.get(asset_id, [])
        if len(prices) < 26:  # Need at least MACD slow period
            out[symbol] = {"rsi": None, "macd": None, "macd_signal": None, "macd_hist": None}
            continue

        df = pd.DataFrame([{
            "date": p.date,
            "close": float(p.close),
        } for p in prices]).set_index("date")

        indicators = compute_indicators(df)

        # Get last row with non-null RSI
        rsi_val = None
        for _, row in indicators.iloc[::-1].iterrows():
            if pd.notna(row["rsi"]):
                rsi_val = round(row["rsi"], 2)
                break

        # Get last row with non-null MACD triplet
        macd_val = macd_sig = macd_hist = None
        for _, row in indicators.iloc[::-1].iterrows():
            if pd.notna(row["macd"]) and pd.notna(row["macd_signal"]) and pd.notna(row["macd_hist"]):
                macd_val = round(row["macd"], 4)
                macd_sig = round(row["macd_signal"], 4)
                macd_hist = round(row["macd_hist"], 4)
                break

        out[symbol] = {
            "rsi": rsi_val,
            "macd": macd_val,
            "macd_signal": macd_sig,
            "macd_hist": macd_hist,
        }

    # Store in cache (single-entry — only latest key matters)
    _indicator_cache.clear()
    _indicator_cache[cache_key] = (out, time.monotonic())

    return out

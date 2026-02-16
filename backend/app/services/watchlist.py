"""Batch indicator computation for the watchlist page."""

from datetime import date, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

import pandas as pd

from app.constants import PERIOD_DAYS, WARMUP_DAYS
from app.models import Asset, PriceHistory
from app.services.indicators import compute_indicators
from app.utils import TTLCache

# In-memory cache for batch indicator snapshots.
# Key: (frozenset of symbols, latest_price_date) — auto-invalidates when prices change.
_indicator_cache: TTLCache = TTLCache(default_ttl=600)


async def compute_and_cache_indicators(db: AsyncSession) -> dict[str, dict]:
    """Compute indicator snapshots for all watchlisted assets, with caching.

    Called by the API endpoint and also by the nightly cron to warm the cache.
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

    cached = _indicator_cache.get_value(cache_key)
    if cached is not None:
        return cached

    # Fetch enough history for indicator warmup (SMA50 needs ~50 trading days)
    warmup_start = date.today() - timedelta(days=PERIOD_DAYS["3mo"] + WARMUP_DAYS)

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
    _indicator_cache.set_value(cache_key, out)

    return out

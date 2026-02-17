"""Batch indicator computation and sparkline data for the watchlist page."""

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

import pandas as pd

from app.constants import PERIOD_DAYS, WARMUP_DAYS
from app.models import PriceHistory
from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.services.compute.indicators import build_indicator_snapshot, compute_indicators
from app.utils import TTLCache

# In-memory cache for batch indicator snapshots.
# Key: (frozenset of symbols, latest_price_date) — auto-invalidates when prices change.
_indicator_cache: TTLCache = TTLCache(default_ttl=600)


async def get_batch_sparklines(db: AsyncSession, period: str = "3mo") -> dict[str, list[dict]]:
    """Return close-price sparkline data for every watchlisted asset."""
    days = PERIOD_DAYS.get(period, 90)
    start = date.today() - timedelta(days=days)

    asset_rows = await AssetRepository(db).list_watchlisted_id_symbol_pairs()
    if not asset_rows:
        return {}

    asset_ids = [r.id for r in asset_rows]
    id_to_symbol = {r.id: r.symbol for r in asset_rows}

    prices = await PriceRepository(db).list_by_assets_since(asset_ids, start)

    out: dict[str, list[dict]] = {sym: [] for sym in id_to_symbol.values()}
    for p in prices:
        sym = id_to_symbol.get(p.asset_id)
        if sym:
            out[sym].append({"date": p.date.isoformat(), "close": round(float(p.close), 4)})

    return out


async def compute_and_cache_indicators(db: AsyncSession) -> dict[str, dict]:
    """Compute indicator snapshots for all watchlisted assets, with caching.

    Called by the API endpoint and also by the nightly cron to warm the cache.
    """
    asset_rows = await AssetRepository(db).list_watchlisted_id_symbol_pairs()
    if not asset_rows:
        return {}

    asset_ids = [r.id for r in asset_rows]
    id_to_symbol = {r.id: r.symbol for r in asset_rows}

    price_repo = PriceRepository(db)

    # Build cache key: symbols + latest price date
    latest_date = await price_repo.get_latest_date(asset_ids)
    cache_key = (frozenset(id_to_symbol.values()), latest_date)

    cached = _indicator_cache.get_value(cache_key)
    if cached is not None:
        return cached

    # Fetch enough history for indicator warmup (SMA50 needs ~50 trading days)
    warmup_start = date.today() - timedelta(days=PERIOD_DAYS["3mo"] + WARMUP_DAYS)

    all_prices = await price_repo.list_by_assets_since(asset_ids, warmup_start)

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

        snapshot = build_indicator_snapshot(compute_indicators(df))

        out[symbol] = {
            "rsi": snapshot.get("rsi"),
            "macd": snapshot.get("macd"),
            "macd_signal": snapshot.get("macd_signal"),
            "macd_hist": snapshot.get("macd_hist"),
        }

    # Store in cache (single-entry — only latest key matters)
    _indicator_cache.clear()
    _indicator_cache.set_value(cache_key, out)

    return out

"""Batch indicator computation and sparkline data for group asset pages."""

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import PERIOD_DAYS, WARMUP_DAYS
from app.models import PriceHistory
from app.repositories.asset_repo import AssetRepository
from app.repositories.group_repo import GroupRepository
from app.repositories.price_repo import PriceRepository
from app.services.compute.indicators import build_indicator_snapshot, compute_indicators
from app.services.compute.utils import prices_to_df
from app.services.fundamentals_cache import merge_fundamentals_from_cache
from app.utils import TTLCache

# In-memory cache for batch indicator snapshots.
# Key: (frozenset of symbols, latest_price_date) — auto-invalidates when prices change.
_indicator_cache: TTLCache = TTLCache(default_ttl=600)


async def _get_default_group_pairs(db: AsyncSession):
    """Get (id, symbol) pairs for assets in the default group."""
    group = await GroupRepository(db).get_default()
    if not group:
        return []
    return await AssetRepository(db).list_in_group_id_symbol_pairs(group.id)


async def get_batch_sparklines(
    db: AsyncSession, period: str = "3mo", group_id: int | None = None,
) -> dict[str, list[dict]]:
    """Return close-price sparkline data for assets in a group.

    If group_id is None, uses the default group.
    """
    days = PERIOD_DAYS.get(period, 90)
    start = date.today() - timedelta(days=days)

    if group_id is not None:
        asset_rows = await AssetRepository(db).list_in_group_id_symbol_pairs(group_id)
    else:
        asset_rows = await _get_default_group_pairs(db)

    if not asset_rows:
        return {}

    asset_ids = [r.id for r in asset_rows]
    id_to_symbol = {r.id: r.symbol for r in asset_rows}

    prices = await PriceRepository(db).list_by_assets_since(asset_ids, start)

    out: dict[str, list[dict]] = {sym: [] for sym in id_to_symbol.values()}
    for p in prices:
        sym = id_to_symbol.get(p.asset_id)
        if sym:
            out[sym].append({"date": p.date.isoformat(), "close": round(p.close, 4)})

    return out


async def compute_and_cache_indicators(
    db: AsyncSession, group_id: int | None = None,
) -> dict[str, dict]:
    """Compute indicator snapshots for assets in a group, with caching.

    If group_id is None, uses the default group.
    """
    if group_id is not None:
        asset_rows = await AssetRepository(db).list_in_group_id_symbol_pairs(group_id)
    else:
        asset_rows = await _get_default_group_pairs(db)

    if not asset_rows:
        return {}

    asset_ids = [r.id for r in asset_rows]
    id_to_symbol = {r.id: r.symbol for r in asset_rows}

    price_repo = PriceRepository(db)

    # Build cache key: symbols + latest price date + group context
    latest_date = await price_repo.get_latest_date(asset_ids)
    cache_key = (frozenset(id_to_symbol.values()), latest_date, group_id)

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
            out[symbol] = {"values": {}}
            continue

        df = prices_to_df(prices)

        snapshot = build_indicator_snapshot(compute_indicators(df))
        out[symbol] = snapshot

    # Merge cached fundamental metrics; background-fetch any misses
    symbols_list = list(id_to_symbol.values())
    merge_fundamentals_from_cache(symbols_list, out)

    _indicator_cache.set_value(cache_key, out)

    return out

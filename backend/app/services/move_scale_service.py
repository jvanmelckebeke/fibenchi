"""Move scales for every tracked symbol, shared by the web board and the companion pulse."""

import asyncio
from collections.abc import Iterable

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AssetRef
from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.schemas.companion import MoveScales
from app.services.compute.move_scale import move_scale_history_start, move_scales
from app.utils import TTLCache

# Keyed and invalidated like the pulse cache: (frozenset of symbols, latest
# stored bar date), dropped by every price write and re-warmed with the pulse.
_move_scale_cache: TTLCache = TTLCache(default_ttl=24 * 3600, max_size=4)


def invalidate_move_scale_cache(symbols: Iterable[str]) -> int:
    """Drop cached scales covering any of ``symbols``. Returns entries removed."""
    wanted = {str(s) for s in symbols}
    if not wanted:
        return 0
    return _move_scale_cache.invalidate(lambda key: bool(key[0] & wanted))


def _compute(refs: list[AssetRef], rows: list[tuple[int, object, float]]) -> dict[str, MoveScales]:
    by_id = {ref.id: ref for ref in refs}
    frame = pd.DataFrame(rows, columns=["asset_id", "date", "close"])
    out: dict[str, MoveScales] = {}
    for asset_id, group in frame.groupby("asset_id", sort=False):
        closes = group.set_index("date")["close"].dropna()
        out[by_id[asset_id].symbol] = move_scales(closes)
    return out


async def book_move_scales(db: AsyncSession) -> dict[str, MoveScales]:
    """symbol -> scales for every symbol in a group or thesis with stored closes."""
    refs = [ref for ref in await AssetRepository(db).list_in_any_group_or_thesis_refs() if ref.id is not None]
    ids = [ref.id for ref in refs]
    latest_date = await PriceRepository(db).get_latest_date(ids)
    cache_key = (frozenset(ref.symbol for ref in refs), latest_date)

    cached = _move_scale_cache.get_value(cache_key)
    if cached is not None:
        return cached

    rows = await PriceRepository(db).list_closes_by_assets_since(ids, move_scale_history_start())
    scales = await asyncio.to_thread(_compute, refs, rows)
    _move_scale_cache.set_value(cache_key, scales)
    return scales

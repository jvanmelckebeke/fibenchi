"""Self-heal stored daily bars that contradict the live quote.

The frontend blanks σ-Move when an asset's latest stored close reconciles with
neither the live price nor the quote's previous close (``isStoredVnrStale`` in
``frontend/src/lib/indicator-registry.ts``). That state means the stored data
is at least two sessions behind the quote — e.g. ``drop_unsettled_last_bar``
discarded a lagging bar and every scheduled sync since missed the symbol, so
once the quote's previous_close rolled at the next open, nothing reconciled.

Rather than waiting up to a day for the next scheduled sync, this job detects
the broken invariant server-side and refreshes just the affected symbols.
"""

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.services.price_providers import get_price_provider
from app.services.price_sync import _reconciles, sync_asset_prices

logger = logging.getLogger(__name__)

# Skip symbols attempted recently: when Yahoo itself is serving unreconcilable
# data (daily feed lagging the quote for hours), a refresh changes nothing and
# retrying every run would just hammer the API.
HEAL_COOLDOWN_SECONDS = 30 * 60

# Bound per-symbol fetches per run. Wider breakage than this is a sync-level
# outage for the scheduled full runs to handle, not the straggler loop.
MAX_HEALS_PER_RUN = 10

_last_attempt: dict[str, float] = {}


async def heal_unreconciled_prices(db: AsyncSession) -> dict[str, int]:
    """Refresh grouped assets whose latest stored bar contradicts the live quote.

    Returns ``{symbol: rows_upserted}`` for the symbols refreshed this run.
    """
    assets = await AssetRepository(db).list_in_any_group()
    if not assets:
        return {}
    by_symbol = {a.symbol: a for a in assets}

    latest = await PriceRepository(db).get_latest_closes([a.id for a in assets])
    quotes = await get_price_provider().batch_fetch_quotes(list(by_symbol))

    stale: list[str] = []
    for q in quotes:
        sym = q.get("symbol")
        if not sym:
            continue
        asset = by_symbol.get(sym)
        if asset is None:
            continue
        stored = latest.get(asset.id)
        if stored is None:  # no bars yet — initial fill is the sync's job
            continue
        price, previous_close = q.get("price"), q.get("previous_close")
        if price is None and previous_close is None:  # dead quote, nothing to anchor on
            continue
        bar_date, bar_close = stored
        if _reconciles(bar_close, price) or _reconciles(bar_close, previous_close):
            continue
        logger.info(
            "%s: stored %s close %s reconciles with neither price %s nor previous_close %s",
            sym, bar_date, bar_close, price, previous_close,
        )
        stale.append(sym)

    if not stale:
        return {}

    now = time.monotonic()
    due = [
        s for s in stale
        if (t := _last_attempt.get(s)) is None or now - t >= HEAL_COOLDOWN_SECONDS
    ]
    skipped_cooldown = len(stale) - len(due)
    deferred = due[MAX_HEALS_PER_RUN:]
    due = due[:MAX_HEALS_PER_RUN]
    if skipped_cooldown or deferred:
        logger.info(
            "Price heal: %d stale symbol(s); healing %d (%d on cooldown, %d deferred to next run)",
            len(stale), len(due), skipped_cooldown, len(deferred),
        )

    healed: dict[str, int] = {}
    for sym in due:
        _last_attempt[sym] = now
        try:
            healed[sym] = await sync_asset_prices(db, by_symbol[sym], period="1mo")
        except Exception:
            logger.warning("Price heal for %s failed", sym, exc_info=True)
    return healed

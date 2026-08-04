"""Self-heal stored daily bars that are wrong or missing.

Two independent repair loops:

- ``heal_unreconciled_prices`` — the *trailing-bar* heal: the frontend blanks
  σ-Move when an asset's latest stored close reconciles with neither the live
  price nor the quote's previous close (``isStoredVnrStale`` in
  ``frontend/src/lib/indicator-registry.ts``). That state means the stored
  data is at least two sessions behind the quote — e.g.
  ``drop_unsettled_last_bar`` discarded a lagging bar and every scheduled sync
  since missed the symbol. Rather than waiting up to a day for the next
  scheduled sync, this detects the broken invariant server-side and refreshes
  just the affected symbols.

- ``heal_interior_holes`` — the *mid-series* heal (issue #559 fix 3): a
  scheduled session with no stored bar (upstream feed hole, NaN-skipped
  upsert, failed nightly sync) silently blanks σ-Move on the bar after it and
  degrades gap-aware indicators. The venue calendar makes such holes exactly
  detectable — expected sessions minus stored dates — and Yahoo usually
  backfills a missing session within a day or two, so a re-fetch of the hole
  range repairs it automatically.
"""

import logging
import time
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.services.market_calendar import Symbol
from app.services.price_providers import get_price_provider
from app.services.price_sync import (
    Anchor,
    _as_date,
    _reconciles,
    sync_asset_prices,
    sync_asset_prices_range,
)

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

    # Carry each stale symbol's reconciliation anchor so the per-symbol refresh
    # below can reuse the quote we already fetched instead of round-tripping to
    # Yahoo again for the same (price, previous_close, market_state) data.
    stale: list[tuple[str, Anchor]] = []
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
        anchor: Anchor = (price, previous_close, q.get("market_state"), _as_date(q.get("session_date")))
        stale.append((sym, anchor))

    if not stale:
        return {}

    now = time.monotonic()
    due = [
        (s, a) for (s, a) in stale
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
    for sym, anchor in due:
        _last_attempt[sym] = now
        try:
            healed[sym] = await sync_asset_prices(db, by_symbol[sym], period="1mo", anchor=anchor)
        except Exception:
            logger.warning("Price heal for %s failed", sym, exc_info=True)
            # This loop shares one session across symbols; roll back a
            # half-applied transaction so it can't poison the next heal.
            await db.rollback()
    return healed


# ---------------------------------------------------------------------------
# Interior-hole heal
# ---------------------------------------------------------------------------

# The hole scan is cheap (one DB query + calendar lookups) but each detected
# hole costs a Yahoo range fetch, and holes either fill on the first try or
# need Yahoo to backfill upstream — rescanning faster gains nothing.
HOLE_SCAN_INTERVAL_SECONDS = 6 * 60 * 60

# A hole that survived a re-fetch is data Yahoo doesn't have (yet). Retry
# daily — backfills typically land within a day or two — instead of every scan.
HOLE_RETRY_COOLDOWN_SECONDS = 24 * 60 * 60

# Bound per-scan fetches; wider breakage is a sync-level outage.
MAX_HOLE_HEALS_PER_SCAN = 5

# Only scan the window that feeds the group snapshot + display periods; ancient
# holes beyond it don't blank anything a user currently sees.
HOLE_SCAN_WINDOW_DAYS = 120

_last_hole_scan: float | None = None
# symbol → (last attempt, the exact holes attempted). A changed hole set is a
# new problem and bypasses the cooldown.
_hole_attempts: dict[str, tuple[float, frozenset[date]]] = {}


def find_interior_holes(stored: set[date], sessions: set[date]) -> set[date]:
    """Scheduled sessions strictly inside the stored range with no stored bar.

    Boundaries are excluded on purpose: a missing *leading* stretch is backfill
    territory (`_ensure_prices`) and a missing *trailing* bar is the
    reconciliation heal's job — this only finds mid-series holes.
    """
    if not stored or not sessions:
        return set()
    first, last = min(stored), max(stored)
    return {d for d in sessions if first < d < last and d not in stored}


async def heal_interior_holes(db: AsyncSession, force: bool = False) -> dict[str, int]:
    """Detect and re-fetch mid-series session holes for grouped assets.

    Returns ``{symbol: rows_upserted}`` for the symbols refreshed this scan.
    Symbols without a resolvable venue calendar are skipped — without the
    session list a hole cannot be told apart from a holiday.
    """
    global _last_hole_scan
    now = time.monotonic()
    if not force and _last_hole_scan is not None and now - _last_hole_scan < HOLE_SCAN_INTERVAL_SECONDS:
        return {}
    _last_hole_scan = now

    assets = await AssetRepository(db).list_in_any_group()
    if not assets:
        return {}

    window_start = date.today() - timedelta(days=HOLE_SCAN_WINDOW_DAYS)
    all_prices = await PriceRepository(db).list_by_assets_since(
        [a.id for a in assets], window_start
    )
    stored_by_asset: dict[int, set[date]] = {}
    for p in all_prices:
        stored_by_asset.setdefault(p.asset_id, set()).add(p.date)

    candidates = []
    for asset in assets:
        stored = stored_by_asset.get(asset.id)
        if not stored or len(stored) < 2:
            continue  # initial fill is the sync's job
        venue = Symbol(asset.symbol).venue
        if venue is None:
            continue
        sessions = venue.session_dates(min(stored), max(stored))
        if not sessions:
            continue
        holes = find_interior_holes(stored, sessions)
        if not holes:
            continue
        signature = frozenset(holes)
        last = _hole_attempts.get(asset.symbol)
        if last and last[1] == signature and now - last[0] < HOLE_RETRY_COOLDOWN_SECONDS:
            continue  # same holes, recently attempted — wait for Yahoo to backfill
        candidates.append((asset, holes, signature))

    if not candidates:
        return {}

    deferred = candidates[MAX_HOLE_HEALS_PER_SCAN:]
    candidates = candidates[:MAX_HOLE_HEALS_PER_SCAN]
    if deferred:
        logger.info(
            "Hole heal: %d symbol(s) with interior holes; healing %d, deferring %d",
            len(candidates) + len(deferred), len(candidates), len(deferred),
        )

    healed: dict[str, int] = {}
    for asset, holes, signature in candidates:
        _hole_attempts[asset.symbol] = (now, signature)
        try:
            count = await sync_asset_prices_range(db, asset, min(holes), max(holes))
            healed[asset.symbol] = count
            refreshed = await PriceRepository(db).list_by_asset_since(asset.id, min(holes))
            remaining = holes - {p.date for p in refreshed}
            if remaining:
                logger.info(
                    "%s: %d of %d interior hole(s) persist after re-fetch "
                    "(Yahoo may backfill later): %s",
                    asset.symbol, len(remaining), len(holes),
                    ", ".join(d.isoformat() for d in sorted(remaining)),
                )
            else:
                logger.info(
                    "%s: healed %d interior hole(s): %s",
                    asset.symbol, len(holes),
                    ", ".join(d.isoformat() for d in sorted(holes)),
                )
        except Exception:
            logger.warning("Hole heal for %s failed", asset.symbol, exc_info=True)
            await db.rollback()
    return healed

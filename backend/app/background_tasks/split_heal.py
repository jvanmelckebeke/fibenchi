"""Repair a stored series whose bars sit in two different share bases.

``normalize_splits`` rebases every frame the provider hands us, so a split can
no longer corrupt anything on the way in. It cannot reach what is already
stored, and it cannot reach bars older than the window a sync fetches: the
scheduled refresh asks for one year, so a split leaves everything before that
in the old basis with a fake cliff at the window edge that the 2y and 5y
charts would render as a real move.

The repair is deliberately not an UPDATE. Re-fetching the symbol across its
whole stored span runs every bar we hold back through the same normalizer, so
the repair path *is* the ingest path with a wider window and cannot invent a
basis of its own. Whatever ``normalize_splits`` decides about the frame it
decides once, for every bar at the same time.

The window is our own oldest stored bar, not ``period="max"``. Asking for
everything the provider has looks like the safer choice and is the opposite:
it writes decades we have no use for (the longest display period is 5y), and
those ancient bars are priced in fractions of a cent, where the table's
four-decimal precision turns ordinary sessions into exact 2x steps. One run
against the real book added ~10,000 MNST rows going back to 1985 and
manufactured 20 fresh discontinuities, which then crowded the actual split out
of the per-run cap.

Detection is a plain SQL scan for a step no session makes, which is cheap and
runs over everything. It proves nothing on its own — the current book's nine
candidates are one split, one currency rebasing (#654) and seven ordinary
earnings days — so the provider's own frame is what settles each one.
"""

import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AssetRef
from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.services.compute.splits import SPLIT_STEP_FACTOR
from app.services.price_providers import get_price_provider
from app.services.price_sync import _NO_ANCHOR, _drop_and_persist, _quote_anchors

logger = logging.getLogger(__name__)

# Bound the per-run fetches, matching the interior-hole heal. Sized so the
# current book's 9 candidates drain in a single run rather than sitting a
# further 6 hours behind a cap.
MAX_SPLIT_HEALS_PER_RUN = 10

# Steps the provider's own history does not resolve, so no split explains them
# and re-fetching again would change nothing. OKLO's real -54% SPAC reprice on
# 2024-05-10 lives here permanently; without it that fetch would repeat on
# every run, forever, to no effect.
#
# Deliberately in memory rather than a table: the set is small, it costs one
# wasted fetch per entry per restart to rebuild, and a stored version would be
# one more piece of durable state to keep honest for no benefit.
_unexplained: set[tuple[str, str]] = set()


def _usable_dates(df: pd.DataFrame) -> set[date]:
    """Dates the frame actually prices.

    A bar the provider lists with a null close is not a price, and
    ``build_price_rows`` skips it rather than storing a NaN — so for the
    purpose of "did the re-fetch cover this date", it did not.
    """
    if df.empty or "close" not in df.columns:
        return set()
    closes = pd.to_numeric(df["close"], errors="coerce")
    return {d for d, c in zip(df.index, closes, strict=False) if pd.notna(c)}


async def _drop_unrebasable_bars(
    db: AsyncSession, ref: AssetRef, df: pd.DataFrame, boundary: date,
) -> int:
    """Delete the stored bar behind a step the re-fetch could not overwrite.

    An upsert only touches the dates it received. When the provider has since
    stopped pricing a date we already hold — Yahoo nulls a session for a day or
    two fairly often, which is why ``heal_interior_holes`` exists — that row
    survives the re-fetch untouched, and after a rebasing it is the one bar
    left in the old basis. MNST 2026-08-10 was exactly this: the whole history
    came back rebased, the 91.43 we already held did not, and the -50% step
    stayed put.

    Such a row cannot be repaired, only removed. A hole is strictly better than
    a lie here, on the same reasoning ``build_price_rows`` skips a NaN bar
    rather than storing it: the gap guard reports a hole honestly and
    ``heal_interior_holes`` refills it once the provider prices that session
    again.

    Scoped to the unpriced bars between the step and the newest bar the provider
    *does* price before it, the step's own bar included — an orphan shows up
    twice, once as the step into it and once as the step out of it, and only
    the first of those has the orphan on the far side. A step whose bars the
    provider prices on both sides is a real session and nothing is deleted,
    which is what keeps this off the seven ordinary earnings days in the
    candidate list. Older holes elsewhere belong to ``heal_interior_holes``.
    """
    priced = _usable_dates(df)
    # The newest bar the provider prices *before* the step. Everything we hold
    # between it and the step is a row the re-fetch could not reach.
    last_priced = max((d for d in priced if d < boundary), default=None)
    if last_priced is None:
        return 0

    stored = await PriceRepository(db).get_dates(ref.id, last_priced, boundary)
    trailing = sorted(d for d in stored if last_priced < d <= boundary and d not in priced)
    if not trailing:
        return 0

    removed = await PriceRepository(db).delete_prices_on(ref.id, trailing)
    if removed:
        logger.info(
            "%s: removed %d bar(s) the provider no longer prices (%s) — they were "
            "the last rows left in the pre-split basis and could not be rebased",
            ref, removed, ", ".join(str(d) for d in trailing),
        )
    return removed


async def heal_split_discontinuities(db: AsyncSession) -> dict[str, int]:
    """Re-fetch full history for assets whose stored bars change basis mid-series.

    Returns ``{symbol: rows_upserted}`` for the symbols repaired this run.
    """
    assets = await AssetRepository(db).list_all()
    if not assets:
        return {}
    # Detached refs: the loop below commits per symbol, which expires live ORM
    # instances and makes any later attribute access raise MissingGreenlet.
    by_id = {a.id: AssetRef.of(a) for a in assets}

    repo = PriceRepository(db)
    candidates: list[tuple[AssetRef, date]] = []
    for asset_id, boundary, prev_close, close in await repo.find_price_steps(SPLIT_STEP_FACTOR):
        ref = by_id.get(asset_id)
        if ref is None or (str(ref), boundary.isoformat()) in _unexplained:
            continue
        # Neutral on purpose. All we know here is the step's size, and most of
        # them turn out to be real sessions. Claiming corruption would cry wolf
        # on every earnings day; the confident wording belongs below, once the
        # provider's own history has settled it.
        logger.info(
            "%s: stored close steps %s -> %s at %s; asking the provider whether "
            "a split explains it",
            ref, prev_close, close, boundary,
        )
        candidates.append((ref, boundary))

    if not candidates:
        return {}

    deferred = len(candidates) - MAX_SPLIT_HEALS_PER_RUN
    if deferred > 0:
        logger.info("Split heal: %d discontinuity(ies) deferred to the next run", deferred)
        candidates = candidates[:MAX_SPLIT_HEALS_PER_RUN]

    provider = get_price_provider()
    healed: dict[str, int] = {}
    for ref, boundary in candidates:
        try:
            # Fetched here rather than through ``sync_asset_prices`` because the
            # reconciliation below needs the frame itself, and fetching the same
            # history twice to see it would be absurd. Persistence is the same
            # ``_drop_and_persist`` every other sync path uses.
            oldest = await repo.get_oldest_date(ref.id)
            if oldest is None:
                continue
            df = await provider.fetch_history(
                ref, start=oldest, end=date.today() + timedelta(days=1),
            )
            anchor = (await _quote_anchors(provider, [ref])).get(ref, _NO_ANCHOR)
            count = await _drop_and_persist(db, ref, df, anchor)
        except Exception:
            logger.warning("%s: full-history re-fetch failed", ref, exc_info=True)
            await db.rollback()
            continue

        if await _still_stepped(repo, ref, boundary):
            count += await _drop_unrebasable_bars(db, ref, df, boundary)

        if await _still_stepped(repo, ref, boundary):
            _unexplained.add((str(ref), boundary.isoformat()))
            logger.warning(
                "%s: the %s step survived a full re-fetch — the provider prices "
                "both bars and no split explains the jump, so it is a real "
                "session. Not retrying; if this is a currency rebasing see #654",
                ref, boundary,
            )
            continue

        healed[str(ref)] = count
        logger.info(
            "%s: rebased onto one share basis, %d bars re-stored (%s resolved)",
            ref, count, boundary,
        )

    return healed


async def _still_stepped(repo: PriceRepository, ref: AssetRef, boundary: date) -> bool:
    """Whether the stored series still jumps into ``boundary``."""
    steps = await repo.find_price_steps(SPLIT_STEP_FACTOR, asset_ids=[ref.id])
    return any(d == boundary for _, d, _, _ in steps)

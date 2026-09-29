"""Fit, store and serve per-venue intraday volume curves.

The curve answers "what fraction of a normal session has traded by now?", which
is what turns volume-so-far into a number comparable with a completed day's —
and with another venue three hours ahead in its own session. See
:mod:`app.services.compute.volume_curve` for the fit itself.

Served from an in-memory cache rather than a query per quote: the quote stream
enriches every symbol on every tick, and the curve changes once a week.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AssetRef
from app.models.volume_curve import VolumeCurvePoint
from app.services.compute.volume_curve import (
    CURVE_BUCKETS,
    MIN_CURVE_SAMPLES,
    fit_curve,
    pace_at,
)
from app.services.market_calendar import Venue
from app.services.yahoo import yahoo_client

logger = logging.getLogger(__name__)

#: Sessions of 5m bars to fit from. Yahoo's 5m window is 60 days; the fit uses
#: whatever of it comes back.
CURVE_FIT_DAYS = 60

#: Symbols per venue to fit from. The curve is the venue's auction structure,
#: so a handful of its liquid names finds it; fetching the whole roster would
#: multiply the Yahoo cost for a median that has already converged.
CURVE_FIT_SYMBOLS_PER_VENUE = 5

_curves: dict[str, list[float]] = {}


def _bucket_frames(
    df: pd.DataFrame, venue: Venue
) -> list[tuple[pd.Series, datetime, datetime]]:
    """Split one symbol's multi-session frame into per-session volume series.

    Each session is paired with its own open and close from the venue calendar,
    so an early close is fitted against its real length rather than a nominal
    one.
    """
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return []

    sessions: list[tuple[pd.Series, datetime, datetime]] = []
    for _, chunk in df.groupby(df.index.date):
        volumes = chunk["volume"].dropna()
        if volumes.empty:
            continue
        # Anchor on a timestamp inside the session: next_open from midnight
        # would return the *following* day's open on a session that has ended.
        anchor = pd.Timestamp(volumes.index[0]).to_pydatetime()
        open_at = _session_open(venue, anchor)
        close_at = venue.next_close(anchor)
        if open_at is None or close_at is None:
            continue
        sessions.append((volumes, open_at, close_at))
    return sessions


def _session_open(venue: Venue, at: datetime) -> datetime | None:
    """The open of the session ``at`` falls inside.

    ``next_open`` looks forward, so from mid-session it returns tomorrow's.
    Stepping back a day and asking forward lands on today's.
    """
    return venue.next_open(at - timedelta(days=1))


async def fit_venue_curves(db: AsyncSession, refs: list[AssetRef]) -> dict[str, int]:
    """Refit every venue represented in ``refs``. Returns {calendar: samples}.

    One venue's failure is logged and skipped; the rest still refit.
    """
    by_calendar: dict[str, list[AssetRef]] = defaultdict(list)
    # Equities only. Crypto and FX trade around the clock with no auction to
    # shape the day, and a curve fitted on them would be a flat line dressed up
    # as a measurement; indices print a synthetic volume that isn't traded.
    for ref in refs:
        if ref.calendar_name is not None and ref.kind.is_equity:
            by_calendar[ref.calendar_name].append(ref)

    fitted: dict[str, int] = {}
    for calendar, cal_refs in by_calendar.items():
        venue = cal_refs[0].venue
        if venue is None:
            continue
        symbols = sorted(r.symbol for r in cal_refs)[:CURVE_FIT_SYMBOLS_PER_VENUE]
        try:
            frames = await yahoo_client.intraday_history(symbols, days=CURVE_FIT_DAYS)
        except Exception:
            logger.exception("Volume curve fetch failed for %s", calendar)
            continue

        sessions: list[tuple[pd.Series, datetime, datetime]] = []
        for df in frames.values():
            sessions.extend(_bucket_frames(df, venue))

        result = fit_curve(sessions)
        if result is None:
            logger.warning("No usable sessions to fit a volume curve for %s", calendar)
            continue
        curve, samples = result
        await _store_curve(db, calendar, curve, samples)
        fitted[calendar] = samples

    await load_curve_cache(db)
    return fitted


async def _store_curve(
    db: AsyncSession, calendar: str, curve: list[float], samples: int
) -> None:
    """Replace a venue's stored curve. Delete-then-insert rather than upsert:
    the bucket count is a constant that could change, and a shrunk curve must
    not leave the tail of the previous one behind it."""
    await db.execute(
        delete(VolumeCurvePoint).where(VolumeCurvePoint.calendar == calendar)
    )
    db.add_all([
        VolumeCurvePoint(
            calendar=calendar,
            bucket=bucket,
            cumulative_fraction=round(value, 5),
            samples=samples,
        )
        for bucket, value in enumerate(curve)
    ])
    await db.commit()


async def load_curve_cache(db: AsyncSession) -> int:
    """Load every stored curve into memory. Returns the number of venues.

    Curves below :data:`MIN_CURVE_SAMPLES` are left out rather than loaded and
    checked at each use — an unusable curve and a missing one produce the same
    answer, so there is no reason for two ways to say it.
    """
    result = await db.execute(
        select(VolumeCurvePoint).order_by(
            VolumeCurvePoint.calendar, VolumeCurvePoint.bucket
        )
    )
    collected: dict[str, list[float]] = defaultdict(list)
    thin: set[str] = set()
    for point in result.scalars():
        if point.samples < MIN_CURVE_SAMPLES:
            thin.add(point.calendar)
            continue
        collected[point.calendar].append(float(point.cumulative_fraction))

    _curves.clear()
    for calendar, curve in collected.items():
        if len(curve) == CURVE_BUCKETS:
            _curves[calendar] = curve
    if thin:
        logger.info(
            "Volume curves below %d samples, not loaded: %s",
            MIN_CURVE_SAMPLES, ", ".join(sorted(thin)),
        )
    return len(_curves)


def curve_cache_size() -> int:
    """Venues with a usable curve loaded. Zero means nothing has been fitted."""
    return len(_curves)


def volume_pace(ref: AssetRef, at: datetime | None = None) -> float | None:
    """Fraction of a normal session's volume this venue has traded by ``at``.

    None whenever the answer would be a guess — no curve fitted, no calendar,
    or the venue is not in its regular session — and the caller then shows the
    settled RVOL rather than an invented live one.
    """
    calendar = ref.calendar_name
    if calendar is None:
        return None
    curve = _curves.get(calendar)
    if curve is None:
        return None
    venue = ref.venue
    if venue is None or not venue.is_open(at):
        return None

    now = at or datetime.now(timezone.utc)
    open_at = _session_open(venue, now)
    close_at = venue.next_close(now)
    if open_at is None or close_at is None:
        return None
    span = (close_at - open_at).total_seconds()
    if span <= 0:
        return None
    return pace_at(curve, (now - open_at).total_seconds() / span)

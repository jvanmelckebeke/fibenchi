"""Scheduler-facing helpers over the venue schedule.

Background jobs and the SSE loop ask these instead of weekday guesses or
sampling live quotes. Both dedupe the portfolio to its venues, so a big
symbol list collapses to a handful of cached Venue objects and zero API
calls — but note their opposite failure postures, each chosen for its
consumer: the gate fails open (never block real work), the poll hint fails
silent (never pin fast polling).
"""

from __future__ import annotations

from datetime import datetime

from app.domain.instrument import classify
from app.services.market_calendar.venue import _as_utc, _venue_for


def any_venue_open(symbols, at: datetime | None = None) -> bool:
    """Whether any symbol's venue is in a tradeable phase (incl. extended hours).

    The scheduler gate: background jobs that only matter while something can
    trade (intraday bar sync, price heal) ask this instead of weekday guesses
    or sampling live quotes.

    Fail-open by design: an unresolvable venue or a failed schedule query
    counts as tradeable. The gate exists to skip certainly-dead ticks, never
    to block real work — a wrong True costs one harmless fetch, a wrong False
    silently stalls data.
    """
    seen: set[str] = set()
    for sym in symbols:
        name = classify(sym).calendar
        if name is None:
            return True  # unknown venue — trading can't be ruled out
        if name in seen:
            continue
        seen.add(name)
        venue = _venue_for(name)
        if venue is None:
            return True  # calendar failed to build — same fail-open rule
        phase = venue.phase(at)
        if phase is None or phase != "closed":
            return True
    return False


_PHASE_RANK = {"closed": 0, "premarket": 1, "aftermarket": 1, "open": 2}


def schedule_poll_hint(symbols, at: datetime | None = None) -> tuple[str, float | None]:
    """The most-active scheduled phase across the symbols' venues, plus the
    seconds until the earliest upcoming regular open.

    Feeds the SSE poll cadence: the live quote feed stays authoritative for
    *speeding up* (it knows about halts and special sessions), while this hint
    backstops it — a dead quote batch during regular hours must not slow
    polling — and lets an all-closed stream sleep exactly until the next bell.

    Unlike :func:`any_venue_open`, unresolvable symbols contribute nothing
    here rather than failing open: a wrong "open" would pin the fast poll
    forever, whereas contributing nothing merely falls back to the live-state
    cadence. Returns ``("closed", None)`` when no venue resolves at all.
    """
    best = "closed"
    next_open_secs: float | None = None
    ts = _as_utc(at).to_pydatetime()
    seen: set[str] = set()
    for sym in symbols:
        name = classify(sym).calendar
        if name is None or name in seen:
            continue
        seen.add(name)
        venue = _venue_for(name)
        if venue is None:
            continue
        phase = venue.phase(ts)
        if phase is not None and _PHASE_RANK.get(phase, 0) > _PHASE_RANK[best]:
            best = phase
        nxt = venue.next_open(ts)
        if nxt is not None:
            secs = (nxt - ts).total_seconds()
            if secs > 0 and (next_open_secs is None or secs < next_open_secs):
                next_open_secs = secs
    return best, next_open_secs

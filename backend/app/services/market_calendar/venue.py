"""The Venue facade — session and schedule queries for one trading venue.

One instance per exchange_calendars calendar, cached for the process
lifetime and shared by every Symbol that resolves to it. All methods return
``None`` on out-of-range or otherwise unanswerable queries — never raise.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd

from app.domain.phases import Phase
from app.services.market_calendar.listings import EXTENDED_HOURS, ExtendedHours

logger = logging.getLogger(__name__)


def _as_utc(at: datetime | None) -> pd.Timestamp:
    ts = pd.Timestamp(at) if at is not None else pd.Timestamp.now(tz=timezone.utc)
    return ts.tz_localize(timezone.utc) if ts.tzinfo is None else ts


class Venue:
    """Schedule facade for one trading venue.

    Bundles the exchange_calendars calendar with the venue's traits (extended
    hours) so callers ask the venue questions instead of re-deriving anything
    from the symbol.
    """

    def __init__(self, name: str, calendar: Any, extended_hours: ExtendedHours | None):
        self.name = name
        self.extended_hours = extended_hours
        self._cal = calendar

    def __repr__(self) -> str:
        return f"Venue({self.name!r})"

    # -- sessions -----------------------------------------------------------

    def session_dates(self, start: date, end: date) -> set[date] | None:
        """All trading sessions in [start, end] (clamped to calendar bounds).

        None when the range can't be answered; an empty set is a real answer.
        """
        try:
            first = max(pd.Timestamp(start), self._cal.first_session)
            last = min(pd.Timestamp(end), self._cal.last_session)
            if first > last:
                return None
            return {ts.date() for ts in self._cal.sessions_in_range(first, last)}
        except Exception:
            logger.warning(
                "Session query failed for %s (%s..%s)", self.name, start, end, exc_info=True
            )
            return None

    def session_dates_for_index(self, index) -> set[date] | None:
        """Sessions covering a price DataFrame's date index (None if unusable).

        Convenience for the indicator pipeline: accepts an index of dates,
        datetimes, or Timestamps and clamps to its min/max range.
        """
        if index is None or len(index) == 0:
            return None
        first, last = index.min(), index.max()
        if isinstance(first, datetime):
            first = first.date()
        if isinstance(last, datetime):
            last = last.date()
        if not isinstance(first, date) or not isinstance(last, date):
            return None
        return self.session_dates(first, last)

    def is_session(self, d: date) -> bool | None:
        sessions = self.session_dates(d, d)
        if sessions is None:
            return None
        return d in sessions

    def recent_sessions(self, d: date, count: int) -> list[date] | None:
        """The ``count`` most recent sessions at or before ``d``, newest first.

        Answers "how many sessions back is this stored bar?" exactly, which is
        the question the σ-Move display needs and cannot ask from two dates
        alone: a client that only knows the current and prior session can
        distinguish "yesterday" from "older", but not "older" from "far too
        old" (#642). Shipping an ordered window lets it read the distance off
        an index instead of counting business days — the heuristic that makes
        every holiday look like a hole (#559, #633).

        ``d`` need not itself be a session. None when the calendar can't answer
        (unknown venue, out of range), and the caller falls back to its
        calendar-less heuristic as everywhere else here; a shorter-than-asked
        list is a real answer (the calendar simply starts later).

        The lookback allows 15 days on top of a week per session requested,
        which clears the longest shutdown any mapped calendar has (Golden Week,
        Lunar New Year) even if it lands mid-window.
        """
        if count <= 0:
            return []
        sessions = self.session_dates(d - timedelta(days=15 + count * 7), d)
        if not sessions:
            return None
        return sorted(sessions, reverse=True)[:count]

    def previous_session(self, d: date) -> date | None:
        """The trading session immediately before ``d`` (exclusive).

        The exact answer to "is this stored bar the session before that quote?"
        — the question the σ-Move display used to approximate by comparing two
        closes within 0.5%, which is a test of how far the price moved rather
        than of which session it was (#626).

        A one-session specialisation of :meth:`recent_sessions`, shifted a day
        to make the bound exclusive, so there is a single lookback
        implementation to get wrong.
        """
        sessions = self.recent_sessions(d - timedelta(days=1), 1)
        return sessions[0] if sessions else None

    def local_date(self, at: datetime | None = None) -> date | None:
        """The venue's local calendar date at ``at`` (UTC now by default).

        The most recent date a daily bar can possibly be *for* — a bar dated
        this or later cannot be a settled prior session. Used by the anchorless
        sync guard to spot a possibly-forming trailing bar without a quote.
        """
        try:
            return _as_utc(at).tz_convert(self._cal.tz).date()
        except Exception:
            return None

    # -- schedule -----------------------------------------------------------

    def is_open(self, at: datetime | None = None) -> bool | None:
        """Whether a *regular* session is running at ``at`` (UTC now default)."""
        try:
            return bool(self._cal.is_open_at_time(_as_utc(at)))
        except Exception:
            return None

    def next_open(self, at: datetime | None = None) -> datetime | None:
        return self._schedule_point("next_open", at)

    def next_close(self, at: datetime | None = None) -> datetime | None:
        return self._schedule_point("next_close", at)

    def previous_close(self, at: datetime | None = None) -> datetime | None:
        return self._schedule_point("previous_close", at)

    def _schedule_point(self, method: str, at: datetime | None) -> datetime | None:
        try:
            return getattr(self._cal, method)(_as_utc(at)).to_pydatetime()
        except Exception:
            return None

    def phase(self, at: datetime | None = None) -> Phase | None:
        """Trading :class:`Phase` at ``at``.

        Regular hours come from the calendar; the extended windows are the
        venue's ``ExtendedHours`` offsets around them. Venues without extended
        hours only ever report OPEN/CLOSED. This is the *scheduled* phase —
        the live authority for what a venue is actually doing right now is the
        quote feed's own market_state; use this for prediction and fallback.
        """
        ts = _as_utc(at)
        try:
            if self._cal.is_open_at_time(ts):
                return Phase.OPEN
            # previous_close is strictly exclusive: at the exact close instant
            # it returns the *prior* session's close, which would misfile the
            # first moment of aftermarket as closed. Nudging the query point
            # one minute forward makes a close at ts count as "just closed";
            # mid-session instants can't reach here (is_open returned above).
            prev_close = self._cal.previous_close(ts + pd.Timedelta(minutes=1))
            nxt_open = self._cal.next_open(ts)
        except Exception:
            return None
        if self.extended_hours is not None:
            if ts < prev_close + self.extended_hours.post_offset:
                return Phase.AFTERMARKET
            if ts >= nxt_open - self.extended_hours.pre_offset:
                return Phase.PREMARKET
        return Phase.CLOSED

    def next_phase_change(self, at: datetime | None = None) -> datetime | None:
        """When :meth:`phase` will next report a different phase.

        The boundaries mirror phase()'s exactly: close for OPEN, the
        extended-hours edges for AFTERMARKET/PREMARKET, and the earlier of
        premarket-start / open for CLOSED. None when the schedule can't be
        answered (same fail-safe posture as everything else here).
        """
        ts = _as_utc(at)
        phase = self.phase(ts)
        if phase is None:
            return None
        try:
            if phase is Phase.OPEN:
                candidate = self._cal.next_close(ts)
            else:
                # Same one-minute nudge as phase(): at the exact close instant,
                # previous_close must mean "the close that just happened".
                prev_close = self._cal.previous_close(ts + pd.Timedelta(minutes=1))
                nxt_open = self._cal.next_open(ts)
                if phase is Phase.AFTERMARKET and self.extended_hours is not None:
                    candidate = prev_close + self.extended_hours.post_offset
                elif phase is Phase.PREMARKET:
                    candidate = nxt_open
                elif (
                    # CLOSED: premarket start if this venue has one and it's
                    # still ahead, else the opening bell.
                    self.extended_hours is not None
                    and ts < (pre_start := nxt_open - self.extended_hours.pre_offset)
                ):
                    candidate = pre_start
                else:
                    candidate = nxt_open
        except Exception:
            return None
        # Always-open calendars (24/7 crypto) have a next_close that isn't a
        # phase change at all — claiming one would be the schedule lying.
        if self.phase(candidate) == phase:
            return None
        return candidate.to_pydatetime()


# One Venue per calendar name, shared by every Symbol that resolves to it.
_venues: dict[str, Venue | None] = {}


def _venue_for(name: str) -> Venue | None:
    if name not in _venues:
        try:
            import exchange_calendars as xcals

            calendar = xcals.get_calendar(name)
            _venues[name] = Venue(name, calendar, EXTENDED_HOURS.get(name))
        except Exception:
            logger.warning("Could not build trading calendar %r", name, exc_info=True)
            _venues[name] = None
    return _venues[name]

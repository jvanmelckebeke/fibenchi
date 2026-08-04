"""Venue trading-calendar resolution and session/schedule queries.

Maps Yahoo Finance symbols to their venue's trading calendar
(``exchange_calendars``) and answers schedule questions: which dates are
trading sessions, when the venue opens/closes, and which phase (premarket /
open / aftermarket / closed) an instant falls in. The primary consumer is
the σ-Move gap guard (issue #559) — with real session dates a missing bar
can be distinguished from an exchange holiday. The schedule/phase side
exists for market-state uses (pre/post-market markers, SSE polling cadence).

Structure: symbol parsing happens in exactly one place
(``MarketCalendarService.calendar_name``); everything venue-specific beyond
that is *data* (the suffix/index tables, the ``EXTENDED_HOURS`` table), and
all schedule questions are answered by a :class:`Venue` object — callers
never branch on ticker shape themselves.

Everything here is fail-safe by design: an unmapped symbol, an unknown
calendar, or a query outside the calendar's bounds returns ``None`` and the
caller falls back to its calendar-less heuristic. A wrong answer from this
module must never be worse than not having it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Yahoo suffix (the part after the last '.') → exchange_calendars name.
# Deliberately limited to venues with an unambiguous mapping; anything else
# resolves to None and downstream keeps its business-day fallback.
SUFFIX_CALENDARS: dict[str, str] = {
    # Euronext
    "AS": "XAMS",  # Amsterdam
    "BR": "XBRU",  # Brussels
    "PA": "XPAR",  # Paris
    "LS": "XLIS",  # Lisbon
    "IR": "XDUB",  # Dublin
    # Rest of Europe
    "DE": "XETR",  # Xetra
    "F": "XFRA",   # Frankfurt floor
    "MI": "XMIL",  # Borsa Italiana
    "L": "XLON",   # London
    "SW": "XSWX",  # SIX Swiss
    "MC": "XMAD",  # Madrid
    "VI": "XWBO",  # Vienna
    "ST": "XSTO",  # Stockholm
    "HE": "XHEL",  # Helsinki
    "OL": "XOSL",  # Oslo
    "WA": "XWAR",  # Warsaw
    "PR": "XPRA",  # Prague
    "BD": "XBUD",  # Budapest
    # (Copenhagen .CO and Athens .AT have no exchange_calendars calendar)
    # Americas
    "TO": "XTSE",  # Toronto
    "MX": "XMEX",  # Mexico
    "SA": "BVMF",  # São Paulo
    "BA": "XBUE",  # Buenos Aires
    "SN": "XSGO",  # Santiago
    # Asia-Pacific
    "T": "XTKS",   # Tokyo
    "HK": "XHKG",  # Hong Kong
    "SS": "XSHG",  # Shanghai
    "SZ": "XSHG",  # Shenzhen — no own calendar; shares national holidays
    "KS": "XKRX",  # Korea
    "KQ": "XKRX",  # KOSDAQ (same holidays)
    "TW": "XTAI",  # Taiwan
    "SI": "XSES",  # Singapore
    "AX": "XASX",  # Australia
    "NZ": "XNZE",  # New Zealand
    # Other
    "JO": "XJSE",  # Johannesburg
    "NS": "XBOM",  # NSE India — XBOM (BSE) shares the national holiday set
    "BO": "XBOM",  # BSE India
}

# Common Yahoo index symbols → calendar of the venue they track.
INDEX_CALENDARS: dict[str, str] = {
    "^AEX": "XAMS",
    "^BFX": "XBRU",
    "^FCHI": "XPAR",
    "^GDAXI": "XETR",
    "^STOXX50E": "XETR",
    "^FTSE": "XLON",
    "^SSMI": "XSWX",
    "^IBEX": "XMAD",
    "^GSPC": "XNYS",
    "^DJI": "XNYS",
    "^IXIC": "XNYS",
    "^NDX": "XNYS",
    "^RUT": "XNYS",
    "^VIX": "XNYS",
    "^N225": "XTKS",
    "^HSI": "XHKG",
}

# Unsuffixed Yahoo symbols are US listings (NYSE/NASDAQ share the holiday set).
DEFAULT_US_CALENDAR = "XNYS"


@dataclass(frozen=True)
class ExtendedHours:
    """A venue's extended-trading window, anchored to the regular session.

    ``pre_offset`` — how long before the regular open premarket starts;
    ``post_offset`` — how long after the regular close aftermarket ends.
    Anchoring to the *actual* schedule (not wall-clock constants) keeps
    half-days correct: on a US early-close day (13:00 ET) aftermarket ends
    17:00 ET, and DST is handled because the calendar's open/close move.
    """

    pre_offset: timedelta
    post_offset: timedelta


# Venues with a real extended-hours session, keyed by calendar name — a data
# table, not per-ticker conditionals. US listings: premarket 4:00 ET
# (= open − 5:30), aftermarket until 20:00 ET (= close + 4:00), matching the
# window Yahoo's PRE/POST market states cover. European venues have auction
# phases, not retail extended sessions, so they are deliberately absent.
EXTENDED_HOURS: dict[str, ExtendedHours] = {
    "XNYS": ExtendedHours(
        pre_offset=timedelta(hours=5, minutes=30), post_offset=timedelta(hours=4)
    ),
}


def _as_utc(at: datetime | None) -> pd.Timestamp:
    ts = pd.Timestamp(at) if at is not None else pd.Timestamp.now(tz=timezone.utc)
    return ts.tz_localize(timezone.utc) if ts.tzinfo is None else ts


class Venue:
    """Schedule facade for one trading venue.

    Bundles the exchange_calendars calendar with the venue's traits (extended
    hours) so callers ask the venue questions instead of re-deriving anything
    from the symbol. All methods return ``None`` on out-of-range or otherwise
    unanswerable queries — never raise.
    """

    def __init__(self, name: str, calendar: Any, extended_hours: ExtendedHours | None):
        self.name = name
        self.extended_hours = extended_hours
        self._cal = calendar

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

    def is_session(self, d: date) -> bool | None:
        sessions = self.session_dates(d, d)
        if sessions is None:
            return None
        return d in sessions

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

    def phase(self, at: datetime | None = None) -> str | None:
        """Trading phase at ``at``: "premarket" | "open" | "aftermarket" | "closed".

        Regular hours come from the calendar; the extended windows are the
        venue's ``ExtendedHours`` offsets around them. Venues without extended
        hours only ever report "open"/"closed". This is the *scheduled* phase —
        the live authority for what a venue is actually doing right now is the
        quote feed's own market_state; use this for prediction and fallback.
        """
        ts = _as_utc(at)
        try:
            if self._cal.is_open_at_time(ts):
                return "open"
            prev_close = self._cal.previous_close(ts)
            nxt_open = self._cal.next_open(ts)
        except Exception:
            return None
        if self.extended_hours is not None:
            if ts < prev_close + self.extended_hours.post_offset:
                return "aftermarket"
            if ts >= nxt_open - self.extended_hours.pre_offset:
                return "premarket"
        return "closed"


class MarketCalendarService:
    """Symbol-addressed access to venue trading calendars.

    ``venue(symbol)`` resolves a Yahoo symbol to a cached :class:`Venue` (one
    per calendar — venues are shared across symbols). The session-query
    convenience methods below exist for the indicator pipeline; schedule and
    phase questions go through the Venue object directly.
    """

    def __init__(self) -> None:
        self._venues: dict[str, Venue | None] = {}

    # -- resolution ---------------------------------------------------------

    @staticmethod
    def calendar_name(symbol: str) -> str | None:
        """Resolve a Yahoo symbol to an exchange_calendars name, or None.

        The single place where ticker shape is interpreted.
        """
        sym = symbol.upper().strip()
        if not sym:
            return None
        if sym in INDEX_CALENDARS:
            return INDEX_CALENDARS[sym]
        if sym.startswith("^"):
            return None  # unknown index — don't guess a venue
        if sym.endswith("=X") or sym.endswith("=F"):
            return None  # FX / futures — not exchange-session shaped
        if "-" in sym:
            return "24/7"  # crypto pairs (BTC-USD): every day is a session
        if "." in sym:
            return SUFFIX_CALENDARS.get(sym.rsplit(".", 1)[1])
        return DEFAULT_US_CALENDAR

    def venue(self, symbol: str) -> Venue | None:
        """The symbol's venue, or None when it can't be resolved/built."""
        name = self.calendar_name(symbol)
        if name is None:
            return None
        if name not in self._venues:
            try:
                import exchange_calendars as xcals

                calendar = xcals.get_calendar(name)
                self._venues[name] = Venue(name, calendar, EXTENDED_HOURS.get(name))
            except Exception:
                logger.warning("Could not build trading calendar %r", name, exc_info=True)
                self._venues[name] = None
        return self._venues[name]

    # -- session conveniences (indicator pipeline) --------------------------

    def session_dates(self, symbol: str, start: date, end: date) -> set[date] | None:
        v = self.venue(symbol)
        return v.session_dates(start, end) if v else None

    def session_dates_for_index(self, symbol: str, index) -> set[date] | None:
        """Sessions covering a price DataFrame's date index (None if unusable).

        Accepts an index of dates, datetimes, or Timestamps and clamps to its
        min/max range.
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
        return self.session_dates(symbol, first, last)

    def is_session(self, symbol: str, d: date) -> bool | None:
        v = self.venue(symbol)
        return v.is_session(d) if v else None


# Shared instance — calendar construction is expensive and venue calendars are
# reusable across symbols and requests.
market_calendar = MarketCalendarService()

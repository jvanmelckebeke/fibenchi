"""Venue trading-calendar resolution and session queries.

Maps Yahoo Finance symbols to their venue's trading calendar
(``exchange_calendars``) and answers schedule questions: which dates are
trading sessions, and when the venue opens/closes. The primary consumer is
the σ-Move gap guard (issue #559) — with real session dates a missing bar
can be distinguished from an exchange holiday. The open/close helpers exist
for market-state uses (pre/post-market markers, SSE polling cadence).

Everything here is fail-safe by design: an unmapped symbol, an unknown
calendar, or a query outside the calendar's bounds returns ``None`` and the
caller falls back to its calendar-less heuristic. A wrong answer from this
module must never be worse than not having it.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
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


class MarketCalendarService:
    """Symbol-addressed access to venue trading calendars.

    Calendar objects are built lazily and cached per calendar name (they are
    shared across symbols on the same venue). All public methods return None
    when no calendar can be resolved or the query falls outside the
    calendar's known range — callers must treat None as "no calendar
    information", not as an answer.
    """

    def __init__(self) -> None:
        self._calendars: dict[str, Any] = {}

    # -- resolution ---------------------------------------------------------

    @staticmethod
    def calendar_name(symbol: str) -> str | None:
        """Resolve a Yahoo symbol to an exchange_calendars name, or None."""
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

    def _calendar(self, name: str) -> Any:
        """Get (and cache) a calendar instance; None if it can't be built."""
        if name not in self._calendars:
            try:
                import exchange_calendars as xcals

                self._calendars[name] = xcals.get_calendar(name)
            except Exception:
                logger.warning("Could not build trading calendar %r", name, exc_info=True)
                self._calendars[name] = None
        return self._calendars[name]

    def _calendar_for(self, symbol: str) -> Any:
        name = self.calendar_name(symbol)
        return self._calendar(name) if name else None

    # -- sessions -----------------------------------------------------------

    def session_dates(self, symbol: str, start: date, end: date) -> set[date] | None:
        """All trading sessions of the symbol's venue in [start, end].

        Returns None when the venue is unknown or the range can't be answered
        (outside calendar bounds after clamping). An empty set is a real
        answer: "no sessions in this range".
        """
        cal = self._calendar_for(symbol)
        if cal is None:
            return None
        try:
            first = max(pd.Timestamp(start), cal.first_session)
            last = min(pd.Timestamp(end), cal.last_session)
            if first > last:
                return None
            return {ts.date() for ts in cal.sessions_in_range(first, last)}
        except Exception:
            logger.warning(
                "Session query failed for %s (%s..%s)", symbol, start, end, exc_info=True
            )
            return None

    def session_dates_for_index(self, symbol: str, index) -> set[date] | None:
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
        return self.session_dates(symbol, first, last)

    def is_session(self, symbol: str, d: date) -> bool | None:
        """Whether the venue trades on date ``d`` (None = unknown venue/range)."""
        sessions = self.session_dates(symbol, d, d)
        if sessions is None:
            return None
        return d in sessions

    # -- schedule (for market-state consumers) ------------------------------

    @staticmethod
    def _as_utc(at: datetime | None) -> pd.Timestamp:
        ts = pd.Timestamp(at) if at is not None else pd.Timestamp.now(tz=timezone.utc)
        return ts.tz_localize(timezone.utc) if ts.tzinfo is None else ts

    def is_open(self, symbol: str, at: datetime | None = None) -> bool | None:
        """Whether the venue is in a regular trading session at ``at`` (UTC now
        by default). Regular hours only — pre/post-market is a venue-data
        concept this calendar doesn't model; derive extended windows from
        next_open/previous_close at the call site.
        """
        cal = self._calendar_for(symbol)
        if cal is None:
            return None
        try:
            return bool(cal.is_open_at_time(self._as_utc(at)))
        except Exception:
            return None

    def next_open(self, symbol: str, at: datetime | None = None) -> datetime | None:
        cal = self._calendar_for(symbol)
        if cal is None:
            return None
        try:
            return cal.next_open(self._as_utc(at)).to_pydatetime()
        except Exception:
            return None

    def next_close(self, symbol: str, at: datetime | None = None) -> datetime | None:
        cal = self._calendar_for(symbol)
        if cal is None:
            return None
        try:
            return cal.next_close(self._as_utc(at)).to_pydatetime()
        except Exception:
            return None

    def previous_close(self, symbol: str, at: datetime | None = None) -> datetime | None:
        cal = self._calendar_for(symbol)
        if cal is None:
            return None
        try:
            return cal.previous_close(self._as_utc(at)).to_pydatetime()
        except Exception:
            return None


# Shared instance — calendar construction is expensive and venue calendars are
# reusable across symbols and requests.
market_calendar = MarketCalendarService()

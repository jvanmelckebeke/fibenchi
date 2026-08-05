"""Symbol → venue trading-calendar resolution and session/schedule queries.

The entry point is :class:`Symbol` — a ``str`` subclass, so it drops in
anywhere a plain ticker string is used — whose ``.venue`` resolves the
symbol's trading venue: ``Symbol("IWDA.AS").venue`` → the XAMS
:class:`Venue`, shared by every symbol on that calendar. The venue answers
session and schedule questions: which dates are trading sessions, when the
venue opens/closes, and which phase (premarket / open / aftermarket /
closed) an instant falls in. ``Symbol.currency`` infers the venue currency
from the same one-pass classification.

The primary consumer is the σ-Move gap guard (issue #559) — with real
session dates (``exchange_calendars``) a missing bar can be distinguished
from an exchange holiday. The schedule side feeds the scheduler gates
(``any_venue_open``), the SSE poll cadence (``schedule_poll_hint``), and
intraday session classification.

Layout: ``listings`` holds the venue trait data (suffix/index tables,
extended hours) — everything venue-specific beyond ticker parsing is *data*
there, and ticker shape is only ever interpreted in ``Symbol``. ``venue``
is the per-calendar facade + cache, ``schedule`` the scheduler-facing
helpers.

Everything here is fail-safe by design: an unmapped symbol, an unknown
calendar, or a query outside the calendar's bounds returns ``None`` and the
caller falls back to its calendar-less heuristic. A wrong answer from this
module must never be worse than not having it.
"""

from app.services.market_calendar.listings import (
    CRYPTO_QUOTE_CURRENCIES,
    DEFAULT_US_CALENDAR,
    EXTENDED_HOURS,
    INDEX_CALENDARS,
    SUFFIX_LISTINGS,
    ExtendedHours,
    Listing,
)
from app.services.market_calendar.schedule import any_venue_open, schedule_poll_hint
from app.services.market_calendar.symbol import Symbol
from app.services.market_calendar.venue import Venue

__all__ = [
    "CRYPTO_QUOTE_CURRENCIES",
    "DEFAULT_US_CALENDAR",
    "EXTENDED_HOURS",
    "INDEX_CALENDARS",
    "SUFFIX_LISTINGS",
    "ExtendedHours",
    "Listing",
    "Symbol",
    "Venue",
    "any_venue_open",
    "schedule_poll_hint",
]

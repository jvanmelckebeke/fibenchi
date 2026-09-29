"""Assemble the companion-app venue calendar from the trading-calendar package.

The companion computes its own indicators from Yahoo bars, but it has no
trading calendar: there is no maintained ``exchange_calendars`` equivalent in
JS, and national-holiday libraries answer a different question (Euronext closes
Good Friday where France works; the NYSE trades through Columbus Day). Without
one, its σ-Move gap guard can't tell a missing bar from an exchange holiday.
We already own the authoritative copy, so we serve it.
"""

from __future__ import annotations

import datetime
import functools

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.assetref import AssetRef
from app.repositories.asset_repo import AssetRepository
from app.schemas.companion import (
    CALENDAR_VERSION,
    CalendarWindow,
    CompanionCalendar,
    HalfDay,
    VenueCalendar,
)
from app.services.market_calendar import venue_for

# The app pulls 6mo of daily bars (126 sessions) and needs sessions covering all
# of them, so ~7 months back; 36 weeks is that plus slack. The forward tail lets
# its poll loop sleep to the next real session open instead of trusting Yahoo's
# currentTradingPeriod, which cannot say "tomorrow is Ascension, sleep 48h".
LOOKBACK_WEEKS = 36
LOOKAHEAD_WEEKS = 3

Window = tuple[datetime.date, datetime.date]


@functools.cache
def known_calendar_names() -> frozenset[str]:
    """Every calendar name exchange_calendars can build."""
    import exchange_calendars as xcals

    return frozenset(xcals.get_calendar_names())


def default_window(today: datetime.date | None = None) -> Window:
    """The default window, anchored to Monday of the current week.

    Anchoring to the week rather than to today is what makes the endpoint's
    ETag hold still. The underlying calendar changes about once a year, but a
    window recomputed per day changes the payload per day, so the app's weekly
    re-sync would never see a 304. For the same reason the router keeps
    ``generatedAt`` out of the ETag digest: it moves on every request, and an
    ETag that can never match is the same as having none.
    """
    today = today or datetime.datetime.now(datetime.UTC).date()
    monday = today - datetime.timedelta(days=today.weekday())
    return (
        monday - datetime.timedelta(weeks=LOOKBACK_WEEKS),
        monday + datetime.timedelta(weeks=LOOKAHEAD_WEEKS),
    )


def build_venue_calendar(name: str, window: Window) -> VenueCalendar | None:
    """One venue's entry, or None when the calendar can't answer for it."""
    venue = venue_for(name)
    if venue is None:
        return None
    start, end = window
    tz_name = venue.tz_name
    week = venue.trading_week(start, end)
    if tz_name is None or week is None:
        return None
    return VenueCalendar(
        timezone=tz_name,
        # ISO numbering (1 = Monday) on the wire; Python's weekday() is 0-based.
        trading_days=sorted(d + 1 for d in week.weekdays),
        closures=week.closures,
        extra_sessions=week.extra_sessions,
        half_days=[
            HalfDay(date=day, close=close) for day, close in (venue.early_closes(start, end) or [])
        ],
    )


async def build_calendar(
    db: AsyncSession,
    venues: list[str] | None = None,
    window: Window | None = None,
) -> CompanionCalendar:
    """Build the calendar bundle for the tracked book, or for ``venues``."""
    window = window or default_window()
    refs: list[AssetRef] = await AssetRepository(db).list_in_any_group_refs()
    symbols = {str(ref): ref.calendar_name for ref in sorted(refs)}

    if venues is None:
        names = sorted({name for name in symbols.values() if name})
    else:
        # Intersected with the known names rather than passed through: venue_for
        # caches a None per name it fails to build, so unrecognised input would
        # grow that cache and log a traceback each time.
        requested = {name.strip().upper() for name in venues}
        names = sorted(requested & known_calendar_names())

    built = {name: build_venue_calendar(name, window) for name in names}

    return CompanionCalendar(
        version=CALENDAR_VERSION,
        generated_at=datetime.datetime.now(datetime.UTC),
        window=CalendarWindow(from_=window[0], to=window[1]),
        venues={name: cal for name, cal in built.items() if cal is not None},
        symbols=symbols,
    )

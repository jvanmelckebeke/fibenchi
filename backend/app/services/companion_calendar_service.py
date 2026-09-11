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


def default_window(today: datetime.date | None = None) -> Window:
    """The default window, anchored to Monday of the current week.

    Anchoring to the week rather than to today is what makes the endpoint's
    ETag hold still: a window recomputed per day changes the payload daily and
    the app's weekly re-sync would never see a 304, even though the underlying
    calendar changes about once a year.
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
    timezone = venue.timezone
    weekdays = venue.trading_weekdays(end)
    closures = venue.closures(start, end)
    if timezone is None or not weekdays or closures is None:
        return None
    return VenueCalendar(
        timezone=timezone,
        # ISO numbering (1 = Monday) on the wire; Python's weekday() is 0-based.
        trading_days=sorted(d + 1 for d in weekdays),
        closures=closures,
        half_days=[
            HalfDay(date=day, close=close) for day, close in (venue.early_closes(start, end) or [])
        ],
    )


async def build_calendar(
    db: AsyncSession,
    venues: list[str] | None = None,
    window: Window | None = None,
) -> CompanionCalendar:
    """Build the calendar bundle for the tracked book, or for ``venues``.

    ``symbols`` always covers the whole tracked book regardless of the venue
    filter: it is the only place the ticker -> venue mapping exists, and making
    it follow the filter would give one field two meanings.
    """
    window = window or default_window()
    refs: list[AssetRef] = await AssetRepository(db).list_in_any_group_refs()
    symbols = {str(ref): ref.calendar_name for ref in sorted(refs)}

    if venues is None:
        names = sorted({name for name in symbols.values() if name})
    else:
        names = sorted({name.strip().upper() for name in venues if name.strip()})

    built = {name: build_venue_calendar(name, window) for name in names}

    return CompanionCalendar(
        version=CALENDAR_VERSION,
        generated_at=datetime.datetime.now(datetime.UTC),
        window=CalendarWindow(from_=window[0], to=window[1]),
        venues={name: cal for name, cal in built.items() if cal is not None},
        symbols=symbols,
    )

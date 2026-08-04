"""Tests for MarketCalendarService — symbol→calendar resolution and session queries.

exchange_calendars ships its holiday data with the package, so these tests are
fully offline. Historical fixtures (2024 holidays, the 2026-08 range from issue
#559) are stable — they can't drift with future calendar updates.
"""

from datetime import date, datetime, timezone

import exchange_calendars as xcals

from app.services.market_calendar import (
    DEFAULT_US_CALENDAR,
    INDEX_CALENDARS,
    SUFFIX_CALENDARS,
    MarketCalendarService,
)

svc = MarketCalendarService()


def test_every_mapped_calendar_exists():
    """Every name in the mapping tables must be a real exchange_calendars
    calendar — a typo here would silently disable the venue's gap detection."""
    names = set(SUFFIX_CALENDARS.values()) | set(INDEX_CALENDARS.values())
    names |= {DEFAULT_US_CALENDAR, "24/7"}
    for name in sorted(names):
        xcals.get_calendar(name)  # raises on unknown names


def test_calendar_name_resolution():
    assert svc.calendar_name("IWDA.AS") == "XAMS"
    assert svc.calendar_name("EUNL.DE") == "XETR"
    assert svc.calendar_name("SWDA.MI") == "XMIL"
    assert svc.calendar_name("IWDA.L") == "XLON"
    assert svc.calendar_name("AAPL") == "XNYS"
    assert svc.calendar_name("^AEX") == "XAMS"
    assert svc.calendar_name("^GSPC") == "XNYS"
    assert svc.calendar_name("BTC-USD") == "24/7"


def test_calendar_name_unknowns_resolve_to_none():
    """Unknown suffixes/indices and non-session instruments must not guess."""
    assert svc.calendar_name("FOO.XX") is None
    assert svc.calendar_name("^UNKNOWNINDEX") is None
    assert svc.calendar_name("EURUSD=X") is None
    assert svc.calendar_name("ES=F") is None
    assert svc.calendar_name("") is None


def test_session_dates_issue_559_range():
    """The exact #559 window: 2026-08-03 was an XAMS session (the feed hole),
    and the weekend days are not."""
    sessions = svc.session_dates("IWDA.AS", date(2026, 7, 29), date(2026, 8, 4))
    assert sessions == {
        date(2026, 7, 29), date(2026, 7, 30), date(2026, 7, 31),
        date(2026, 8, 3), date(2026, 8, 4),
    }


def test_session_dates_knows_holidays():
    """Easter Monday 2024 (Apr 1) closed Euronext but is a plain business day."""
    sessions = svc.session_dates("IWDA.AS", date(2024, 3, 28), date(2024, 4, 2))
    assert sessions == {date(2024, 3, 28), date(2024, 4, 2)}  # Good Friday + Easter Monday closed
    assert svc.is_session("IWDA.AS", date(2024, 4, 1)) is False
    # The same Monday was a session in New York.
    assert svc.is_session("AAPL", date(2024, 4, 1)) is True


def test_session_dates_unknown_symbol_is_none():
    assert svc.session_dates("FOO.XX", date(2024, 1, 1), date(2024, 1, 31)) is None


def test_session_dates_for_index_handles_dates_and_timestamps():
    import pandas as pd

    by_date = svc.session_dates_for_index(
        "AAPL", pd.Index([date(2024, 4, 1), date(2024, 4, 5)])
    )
    by_ts = svc.session_dates_for_index(
        "AAPL", pd.bdate_range("2024-04-01", "2024-04-05")
    )
    assert by_date == by_ts
    assert by_date is not None and date(2024, 4, 2) in by_date
    # Non-date index → no calendar info rather than an exception.
    assert svc.session_dates_for_index("AAPL", pd.RangeIndex(5)) is None
    assert svc.session_dates_for_index("AAPL", pd.Index([])) is None


def test_crypto_weekends_are_sessions():
    sessions = svc.session_dates("BTC-USD", date(2026, 8, 1), date(2026, 8, 2))
    assert sessions == {date(2026, 8, 1), date(2026, 8, 2)}  # Sat + Sun


def test_open_close_helpers():
    """Regular-hours schedule for a fixed historical instant (offline data)."""
    # Wednesday 2024-04-03, 15:00 UTC: NYSE regular session (13:30–20:00 UTC).
    at = datetime(2024, 4, 3, 15, 0, tzinfo=timezone.utc)
    venue = svc.venue("AAPL")
    assert venue is not None
    assert venue.is_open(at) is True
    assert venue.is_open(datetime(2024, 4, 3, 21, 0, tzinfo=timezone.utc)) is False
    assert venue.next_close(at) == datetime(2024, 4, 3, 20, 0, tzinfo=timezone.utc)
    # Unknown venue: resolution answers None, never raises.
    assert svc.venue("FOO.XX") is None


def test_venues_are_cached_and_shared():
    """Symbols on the same venue share one Venue instance."""
    assert svc.venue("AAPL") is svc.venue("MSFT")
    assert svc.venue("^GSPC") is svc.venue("AAPL")


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_phase_us_regular_day():
    """US venue phases across Wednesday 2024-04-03 (regular 13:30–20:00 UTC).

    Premarket = open − 5:30 (4:00 ET), aftermarket until close + 4:00 (20:00 ET).
    """
    venue = svc.venue("AAPL")
    assert venue is not None
    assert venue.phase(_utc(2024, 4, 3, 7, 0)) == "closed"       # 3:00 ET
    assert venue.phase(_utc(2024, 4, 3, 8, 0)) == "premarket"    # 4:00 ET sharp
    assert venue.phase(_utc(2024, 4, 3, 12, 0)) == "premarket"   # 8:00 ET
    assert venue.phase(_utc(2024, 4, 3, 15, 0)) == "open"
    assert venue.phase(_utc(2024, 4, 3, 21, 0)) == "aftermarket"  # 17:00 ET
    assert venue.phase(_utc(2024, 4, 4, 1, 0)) == "closed"       # 21:00 ET Apr 3


def test_phase_us_half_day():
    """Early-close day (day after Thanksgiving 2023: close 13:00 ET / 18:00 UTC).

    Because the extended window is anchored to the actual close, aftermarket
    ends 17:00 ET — a hardcoded 20:00 ET would misreport this.
    """
    venue = svc.venue("AAPL")
    assert venue is not None
    assert venue.phase(_utc(2023, 11, 24, 17, 0)) == "open"          # 12:00 ET
    assert venue.phase(_utc(2023, 11, 24, 20, 0)) == "aftermarket"   # 15:00 ET
    assert venue.phase(_utc(2023, 11, 24, 23, 0)) == "closed"        # 18:00 ET
    # A normal close+4h instant on a *regular* day is still aftermarket.
    assert venue.phase(_utc(2023, 11, 27, 23, 0)) == "aftermarket"


def test_phase_weekend_is_closed():
    """Saturday sits between Friday's aftermarket and Monday's premarket."""
    venue = svc.venue("AAPL")
    assert venue is not None
    assert venue.phase(_utc(2024, 4, 6, 15, 0)) == "closed"


def test_phase_venue_without_extended_hours():
    """European venues have no retail extended session: open/closed only."""
    venue = svc.venue("IWDA.AS")
    assert venue is not None
    assert venue.extended_hours is None
    # XAMS regular hours 09:00–17:30 CEST = 07:00–15:30 UTC on 2024-04-03.
    assert venue.phase(_utc(2024, 4, 3, 10, 0)) == "open"
    assert venue.phase(_utc(2024, 4, 3, 16, 0)) == "closed"  # 18:00 CEST
    assert venue.phase(_utc(2024, 4, 3, 6, 0)) == "closed"   # 08:00 CEST

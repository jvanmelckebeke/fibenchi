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
    assert svc.is_open("AAPL", at) is True
    assert svc.is_open("AAPL", datetime(2024, 4, 3, 21, 0, tzinfo=timezone.utc)) is False
    next_close = svc.next_close("AAPL", at)
    assert next_close == datetime(2024, 4, 3, 20, 0, tzinfo=timezone.utc)
    # Unknown venue: all schedule helpers answer None, never raise.
    assert svc.is_open("FOO.XX", at) is None
    assert svc.next_open("FOO.XX", at) is None

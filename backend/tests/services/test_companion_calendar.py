import datetime

from app.schemas.companion import HalfDay
from app.services.companion_calendar_service import build_venue_calendar, default_window

# Christmas week: XNYS shuts on the 25th and half-closes on the 24th, XPAR shuts
# on the 26th too. Fixed dates, so the assertions don't drift with the clock.
XMAS_WINDOW = (datetime.date(2025, 12, 1), datetime.date(2026, 1, 15))


def test_known_holidays_and_half_days_are_listed():
    nyse = build_venue_calendar("XNYS", XMAS_WINDOW)
    assert nyse.timezone == "America/New_York"
    assert datetime.date(2025, 12, 25) in nyse.closures
    assert datetime.date(2026, 1, 1) in nyse.closures
    assert nyse.half_days == [HalfDay(date=datetime.date(2025, 12, 24), close=datetime.time(13, 0))]

    paris = build_venue_calendar("XPAR", XMAS_WINDOW)
    assert paris.timezone == "Europe/Paris"
    # Boxing Day is a Euronext closure and not an NYSE one — the venues are
    # genuinely distinct, not one table copied.
    assert datetime.date(2025, 12, 26) in paris.closures
    assert datetime.date(2025, 12, 26) not in nyse.closures
    assert (datetime.date(2025, 12, 24), datetime.time(14, 5)) in [
        (h.date, h.close) for h in paris.half_days
    ]


def test_closures_stay_inside_the_window():
    nyse = build_venue_calendar("XNYS", XMAS_WINDOW)
    assert nyse.closures == sorted(nyse.closures)
    assert all(XMAS_WINDOW[0] <= d <= XMAS_WINDOW[1] for d in nyse.closures)
    # Thanksgiving 2025 sits just before the window and must not leak in.
    assert datetime.date(2025, 11, 27) not in nyse.closures


def test_trading_week_is_read_off_the_calendar():
    # ISO numbering: XSAU runs Sunday-Thursday, so it has no Friday (5) and no
    # Saturday (6). Weekends are not derivable from "Mon-Fri" on the client.
    assert build_venue_calendar("XSAU", XMAS_WINDOW).trading_days == [1, 2, 3, 4, 7]
    assert build_venue_calendar("XNYS", XMAS_WINDOW).trading_days == [1, 2, 3, 4, 5]
    assert build_venue_calendar("24/7", XMAS_WINDOW).trading_days == [1, 2, 3, 4, 5, 6, 7]


def test_unbuildable_calendar_is_none():
    assert build_venue_calendar("NOT-A-CALENDAR", XMAS_WINDOW) is None


def test_default_window_is_anchored_to_monday():
    # Anchoring to the week is what lets the ETag hold still between the app's
    # weekly re-syncs; every day of a week must produce the same window.
    monday = datetime.date(2026, 9, 7)
    windows = {default_window(monday + datetime.timedelta(days=n)) for n in range(7)}
    assert len(windows) == 1
    start, end = windows.pop()
    assert start.weekday() == 0 and end.weekday() == 0
    assert (end - start).days > 240

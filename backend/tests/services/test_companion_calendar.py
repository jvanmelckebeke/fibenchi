import datetime

from app.schemas.companion import HalfDay
from app.services.companion_calendar_service import build_venue_calendar, default_window

XMAS_WINDOW = (datetime.date(2025, 12, 1), datetime.date(2026, 1, 15))


def test_known_holidays_and_half_days_are_listed():
    nyse = build_venue_calendar("XNYS", XMAS_WINDOW)
    assert nyse.timezone == "America/New_York"
    assert datetime.date(2025, 12, 25) in nyse.closures
    assert datetime.date(2026, 1, 1) in nyse.closures
    assert nyse.half_days == [HalfDay(date=datetime.date(2025, 12, 24), close=datetime.time(13, 0))]

    paris = build_venue_calendar("XPAR", XMAS_WINDOW)
    assert paris.timezone == "Europe/Paris"
    assert datetime.date(2025, 12, 26) in paris.closures
    assert datetime.date(2025, 12, 26) not in nyse.closures
    assert (datetime.date(2025, 12, 24), datetime.time(14, 5)) in [
        (h.date, h.close) for h in paris.half_days
    ]


def test_closures_stay_inside_the_window():
    nyse = build_venue_calendar("XNYS", XMAS_WINDOW)
    assert nyse.closures == sorted(nyse.closures)
    assert all(XMAS_WINDOW[0] <= d <= XMAS_WINDOW[1] for d in nyse.closures)
    assert datetime.date(2025, 11, 27) not in nyse.closures  # Thanksgiving, just outside


def test_trading_week_is_read_off_the_calendar():
    assert build_venue_calendar("XSAU", XMAS_WINDOW).trading_days == [1, 2, 3, 4, 7]
    assert build_venue_calendar("XNYS", XMAS_WINDOW).trading_days == [1, 2, 3, 4, 5]
    assert build_venue_calendar("24/7", XMAS_WINDOW).trading_days == [1, 2, 3, 4, 5, 6, 7]


def test_changed_trading_week_reports_the_current_one():
    # Tel Aviv moved from Sunday-Thursday to Monday-Friday in January 2026. A
    # week taken as the union over the window would report six trading days and
    # turn every Sunday after the switch into a closure.
    xtae = build_venue_calendar("XTAE", (datetime.date(2025, 12, 29), datetime.date(2026, 9, 28)))
    assert xtae.trading_days == [1, 2, 3, 4, 5]
    assert not any(d.weekday() == 6 for d in xtae.closures)
    # The sessions from before the switch are still described, as exceptions.
    assert xtae.extra_sessions == [datetime.date(2026, 1, 4)]


def test_session_rule_reproduces_the_calendar():
    # The contract's promise to the app: a date is a session iff it is an extra
    # session, or its weekday is a trading day and it is not a closure.
    import exchange_calendars as xcals

    window = (datetime.date(2025, 12, 29), datetime.date(2026, 9, 28))
    for name in ("XNYS", "XPAR", "XTAE", "XSAU", "24/7"):
        cal = build_venue_calendar(name, window)
        trading = {d - 1 for d in cal.trading_days}
        closures, extra = set(cal.closures), set(cal.extra_sessions)
        derived = {
            d for d in (window[0] + datetime.timedelta(n) for n in range((window[1] - window[0]).days + 1))
            if d in extra or (d.weekday() in trading and d not in closures)
        }
        actual = {
            ts.date() for ts in xcals.get_calendar(name).sessions_in_range(str(window[0]), str(window[1]))
        }
        assert derived == actual, name


def test_unbuildable_calendar_is_none():
    assert build_venue_calendar("NOT-A-CALENDAR", XMAS_WINDOW) is None


def test_default_window_is_anchored_to_monday():
    monday = datetime.date(2026, 9, 7)
    windows = {default_window(monday + datetime.timedelta(days=n)) for n in range(7)}
    assert len(windows) == 1
    start, end = windows.pop()
    assert start.weekday() == 0 and end.weekday() == 0
    assert (end - start).days > 240

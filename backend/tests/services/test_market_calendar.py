"""Tests for market_calendar + AssetRef — ticker→venue resolution and session/schedule queries.

exchange_calendars ships its holiday data with the package, so these tests are
fully offline. Historical fixtures (2024 holidays, the 2026-08 range from issue
#559) are stable — they can't drift with future calendar updates.
"""

from datetime import date, datetime, timezone

import exchange_calendars as xcals

from app.domain import AssetKind, AssetRef
from app.services.market_calendar import (
    DEFAULT_US_CALENDAR,
    INDEX_CALENDARS,
    SUFFIX_LISTINGS,
    any_venue_open,
)


def test_every_mapped_calendar_exists():
    """Every name in the mapping tables must be a real exchange_calendars
    calendar — a typo here would silently disable the venue's gap detection."""
    names = {li.calendar for li in SUFFIX_LISTINGS.values() if li.calendar}
    names |= set(INDEX_CALENDARS.values())
    names |= {DEFAULT_US_CALENDAR, "24/7"}
    for name in sorted(names):
        xcals.get_calendar(name)  # raises on unknown names


def test_calendar_name_resolution():
    assert AssetRef("IWDA.AS").calendar_name == "XAMS"
    assert AssetRef("EUNL.DE").calendar_name == "XETR"
    assert AssetRef("SWDA.MI").calendar_name == "XMIL"
    assert AssetRef("IWDA.L").calendar_name == "XLON"
    assert AssetRef("AAPL").calendar_name == "XNYS"
    assert AssetRef("^AEX").calendar_name == "XAMS"
    assert AssetRef("^GSPC").calendar_name == "XNYS"
    assert AssetRef("BTC-USD").calendar_name == "24/7"


def test_hyphenated_us_listings_are_not_crypto():
    """US class shares and preferreds are hyphenated but trade on XNYS —
    routing them to the 24/7 calendar would flag every weekend as a data gap
    and suppress their σ-Move each Monday."""
    assert AssetRef("BRK-B").calendar_name == "XNYS"
    assert AssetRef("BF-B").calendar_name == "XNYS"
    assert AssetRef("BAC-PL").calendar_name == "XNYS"
    assert AssetRef("ETH-EUR").calendar_name == "24/7"
    assert AssetRef("SOL-BTC").calendar_name == "24/7"


def test_calendar_name_unknowns_resolve_to_none():
    """Unknown suffixes/indices and non-session instruments must not guess."""
    assert AssetRef("FOO.XX").calendar_name is None
    assert AssetRef("^UNKNOWNINDEX").calendar_name is None
    assert AssetRef("EURUSD=X").calendar_name is None
    assert AssetRef("ES=F").calendar_name is None
    assert AssetRef("").calendar_name is None
    assert AssetRef("FOO.XX").venue is None


def test_symbol_is_a_str():
    """Symbol must stay a drop-in for plain ticker strings."""
    sym = AssetRef("IWDA.AS")
    assert sym == "IWDA.AS"
    assert {sym: 1}["IWDA.AS"] == 1
    assert {"IWDA.AS": 1}[sym] == 1


def test_session_dates_issue_559_range():
    """The exact #559 window: 2026-08-03 was an XAMS session (the feed hole),
    and the weekend days are not."""
    sessions = AssetRef("IWDA.AS").venue.session_dates(date(2026, 7, 29), date(2026, 8, 4))
    assert sessions == {
        date(2026, 7, 29), date(2026, 7, 30), date(2026, 7, 31),
        date(2026, 8, 3), date(2026, 8, 4),
    }


def test_session_dates_knows_holidays():
    """Easter Monday 2024 (Apr 1) closed Euronext but is a plain business day."""
    xams = AssetRef("IWDA.AS").venue
    sessions = xams.session_dates(date(2024, 3, 28), date(2024, 4, 2))
    assert sessions == {date(2024, 3, 28), date(2024, 4, 2)}  # Good Friday + Easter Monday closed
    assert xams.is_session(date(2024, 4, 1)) is False
    # The same Monday was a session in New York.
    assert AssetRef("AAPL").venue.is_session(date(2024, 4, 1)) is True


def test_session_dates_for_index_handles_dates_and_timestamps():
    import pandas as pd

    xnys = AssetRef("AAPL").venue
    by_date = xnys.session_dates_for_index(pd.Index([date(2024, 4, 1), date(2024, 4, 5)]))
    by_ts = xnys.session_dates_for_index(pd.bdate_range("2024-04-01", "2024-04-05"))
    assert by_date == by_ts
    assert by_date is not None and date(2024, 4, 2) in by_date
    # Non-date index → no calendar info rather than an exception.
    assert xnys.session_dates_for_index(pd.RangeIndex(5)) is None
    assert xnys.session_dates_for_index(pd.Index([])) is None


def test_crypto_weekends_are_sessions():
    sessions = AssetRef("BTC-USD").venue.session_dates(date(2026, 8, 1), date(2026, 8, 2))
    assert sessions == {date(2026, 8, 1), date(2026, 8, 2)}  # Sat + Sun


def test_open_close_helpers():
    """Regular-hours schedule for a fixed historical instant (offline data)."""
    # Wednesday 2024-04-03, 15:00 UTC: NYSE regular session (13:30–20:00 UTC).
    at = datetime(2024, 4, 3, 15, 0, tzinfo=timezone.utc)
    venue = AssetRef("AAPL").venue
    assert venue is not None
    assert venue.is_open(at) is True
    assert venue.is_open(datetime(2024, 4, 3, 21, 0, tzinfo=timezone.utc)) is False
    assert venue.next_close(at) == datetime(2024, 4, 3, 20, 0, tzinfo=timezone.utc)


def test_venues_are_cached_and_shared():
    """Symbols on the same venue share one Venue instance."""
    assert AssetRef("AAPL").venue is AssetRef("MSFT").venue
    assert AssetRef("^GSPC").venue is AssetRef("AAPL").venue


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_phase_us_regular_day():
    """US venue phases across Wednesday 2024-04-03 (regular 13:30–20:00 UTC).

    Premarket = open − 5:30 (4:00 ET), aftermarket until close + 4:00 (20:00 ET).
    """
    venue = AssetRef("AAPL").venue
    assert venue.phase(_utc(2024, 4, 3, 7, 0)) == "closed"       # 3:00 ET
    assert venue.phase(_utc(2024, 4, 3, 8, 0)) == "premarket"    # 4:00 ET sharp
    assert venue.phase(_utc(2024, 4, 3, 12, 0)) == "premarket"   # 8:00 ET
    assert venue.phase(_utc(2024, 4, 3, 15, 0)) == "open"
    assert venue.phase(_utc(2024, 4, 3, 20, 0)) == "aftermarket"  # 16:00 ET sharp
    assert venue.phase(_utc(2024, 4, 3, 21, 0)) == "aftermarket"  # 17:00 ET
    assert venue.phase(_utc(2024, 4, 4, 1, 0)) == "closed"       # 21:00 ET Apr 3


def test_phase_us_half_day():
    """Early-close day (day after Thanksgiving 2023: close 13:00 ET / 18:00 UTC).

    Because the extended window is anchored to the actual close, aftermarket
    ends 17:00 ET — a hardcoded 20:00 ET would misreport this.
    """
    venue = AssetRef("AAPL").venue
    assert venue.phase(_utc(2023, 11, 24, 17, 0)) == "open"          # 12:00 ET
    assert venue.phase(_utc(2023, 11, 24, 20, 0)) == "aftermarket"   # 15:00 ET
    assert venue.phase(_utc(2023, 11, 24, 23, 0)) == "closed"        # 18:00 ET
    # A normal close+4h instant on a *regular* day is still aftermarket.
    assert venue.phase(_utc(2023, 11, 27, 23, 0)) == "aftermarket"


def test_phase_weekend_is_closed():
    """Saturday sits between Friday's aftermarket and Monday's premarket."""
    assert AssetRef("AAPL").venue.phase(_utc(2024, 4, 6, 15, 0)) == "closed"


def test_phase_venue_without_extended_hours():
    """European venues have no retail extended session: open/closed only."""
    venue = AssetRef("IWDA.AS").venue
    assert venue.extended_hours is None
    # XAMS regular hours 09:00–17:30 CEST = 07:00–15:30 UTC on 2024-04-03.
    assert venue.phase(_utc(2024, 4, 3, 10, 0)) == "open"
    assert venue.phase(_utc(2024, 4, 3, 16, 0)) == "closed"  # 18:00 CEST
    assert venue.phase(_utc(2024, 4, 3, 6, 0)) == "closed"   # 08:00 CEST


def test_any_venue_open_all_closed_weekend():
    """Saturday noon UTC: neither New York nor Amsterdam trades."""
    assert any_venue_open(["AAPL", "MSFT", "IWDA.AS"], _utc(2024, 4, 6, 12, 0)) is False


def test_any_venue_open_crypto_keeps_weekend_alive():
    """The 24/7 calendar makes a crypto pair defeat the weekend gate — the old
    weekday() guard wrongly skipped crypto all weekend."""
    assert any_venue_open(["AAPL", "BTC-USD"], _utc(2024, 4, 6, 12, 0)) is True


def test_any_venue_open_extended_hours_count():
    """US aftermarket (Wed 21:00 UTC) is a tradeable phase even with XAMS closed."""
    assert any_venue_open(["IWDA.AS", "AAPL"], _utc(2024, 4, 3, 21, 0)) is True


def test_any_venue_open_us_holiday():
    """July 4 2024 (Thursday) 15:00 UTC — normally mid-session, but a holiday.
    The old weekday() gate would have run the jobs all day."""
    assert any_venue_open(["AAPL"], _utc(2024, 7, 4, 15, 0)) is False


def test_any_venue_open_fails_open_on_unknown_venue():
    """An unresolvable symbol must never let the gate block real work."""
    assert any_venue_open(["FOO.XX"], _utc(2024, 4, 6, 12, 0)) is True
    assert any_venue_open([], _utc(2024, 4, 6, 12, 0)) is False


def test_schedule_poll_hint_phases_and_next_open():
    from app.services.market_calendar import schedule_poll_hint

    # Wednesday 15:00 UTC: XNYS session running.
    phase, _ = schedule_poll_hint(["AAPL", "IWDA.AS"], _utc(2024, 4, 3, 15, 0))
    assert phase == "open"
    # Saturday: everything closed; next open is Monday, far away.
    phase, secs = schedule_poll_hint(["AAPL"], _utc(2024, 4, 6, 12, 0))
    assert phase == "closed"
    assert secs is not None and secs > 3600
    # Two minutes before the Amsterdam bell: closed, but the bell is near.
    phase, secs = schedule_poll_hint(["IWDA.AS"], _utc(2024, 4, 8, 6, 58))
    assert phase == "closed"
    assert secs is not None and 0 < secs <= 130
    # Unresolvable symbols contribute nothing (no fail-open here).
    assert schedule_poll_hint(["FOO.XX"], _utc(2024, 4, 6, 12, 0)) == ("closed", None)


def test_symbol_currency_shapes():
    """Currency inference per ticker shape (fallback for absent Yahoo data)."""
    assert AssetRef("IWDA.AS").currency == "EUR"
    assert AssetRef("NOVO-B.CO").currency == "DKK"  # hyphenated class + suffix
    assert AssetRef("AAPL").currency == "USD"
    assert AssetRef("BRK-B").currency == "USD"
    assert AssetRef("BTC-EUR").currency == "EUR"  # fiat quote leg
    assert AssetRef("SOL-BTC").currency is None   # crypto-quoted: no display fiat
    assert AssetRef("^GSPC").currency is None
    assert AssetRef("EURUSD=X").currency is None
    assert AssetRef("FOO.ZZ").currency is None


def test_new_calendar_coverage():
    """Suffixes that had currency-but-no-calendar now resolve venues too."""
    assert AssetRef("NOVO-B.CO").calendar_name == "XCSE"
    assert AssetRef("OPAP.AT").calendar_name == "ASEX"
    assert AssetRef("TEVA.TA").calendar_name == "XTAE"
    # Tadawul trades Sunday–Thursday: a plain Sunday is a session, Friday not.
    assert AssetRef("2222.SR").venue.is_session(date(2024, 1, 7)) is True
    assert AssetRef("2222.SR").venue.is_session(date(2024, 1, 5)) is False
    # Qatar has a currency but no exchange_calendars calendar.
    assert AssetRef("QNBK.QA").calendar_name is None
    assert AssetRef("QNBK.QA").currency == "QAR"


# --- AssetRef -------------------------------------------------------------

def test_asset_ref_is_a_ticker_with_optional_id():
    """One domain object, both faces: a str drop-in ticker with venue traits,
    optionally bound to a stored asset id."""
    ref = AssetRef("IWDA.AS", 1)
    assert ref == "IWDA.AS"  # str drop-in: equality/hash are the ticker's
    assert ref.id == 1
    assert ref.currency == "EUR"
    assert ref.venue is AssetRef("IWDA.AS").venue
    assert AssetRef("IWDA.AS").id is None  # unbound: just a classified ticker
    assert {ref: "x"}["IWDA.AS"] == "x"  # id never affects keying


def test_asset_ref_kind_captures_the_classification():
    """The if-chain runs once; every shape decision it makes is queryable
    afterwards — downstream never re-inspects ticker characters."""
    assert AssetRef("AAPL").kind.is_equity
    assert AssetRef("IWDA.AS").kind.is_equity  # ETFs are listed securities
    assert AssetRef("^GSPC").kind.is_index
    assert AssetRef("^AEX").kind.is_index  # mapped index: kind + calendar
    assert AssetRef("^AEX").calendar_name == "XAMS"
    assert AssetRef("EURUSD=X").kind.is_fx
    assert AssetRef("ES=F").kind.is_future
    assert AssetRef("BTC-USD").kind.is_crypto
    assert AssetRef("BRK-B").kind.is_equity  # hyphenated class, not crypto
    assert AssetRef("").kind is AssetKind.UNKNOWN
    assert not AssetRef("ES=F").kind.is_fx  # traits are mutually exclusive


def test_asset_ref_of_duck_types():
    """AssetRef.of accepts anything with symbol/id — an ORM Asset (while
    live) or another ref."""

    class FakeAsset:
        id = 7
        symbol = "AAPL"

    ref = AssetRef.of(FakeAsset())
    assert (str(ref), ref.id) == ("AAPL", 7)
    assert AssetRef.of(ref) == ref
    assert repr(ref) == "AssetRef('AAPL', id=7)"

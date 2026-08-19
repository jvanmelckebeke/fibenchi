"""Unit tests for quote_service — REST parsing, SSE delta compression, adaptive intervals."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain import AssetRef
from app.schemas.intraday import IntradayBar
from app.schemas.quote import Quote
from app.services.compute.indicators import VNR_MAX_SESSIONS_BEHIND
from app.services.quote_service import (
    QUOTE_SESSION_WINDOW,
    _reset_asset_list_cache,
    attach_recent_sessions,
    get_quotes,
    quote_event_generator,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


@pytest.fixture(autouse=True)
def _clear_roster_cache():
    """The roster cache is module state with a 30s TTL, so without this a test
    silently inherits the previous test's symbols. Every test here used AAPL
    until one didn't, and it failed only when run alongside the others."""
    _reset_asset_list_cache()
    yield
    _reset_asset_list_cache()


def _mock_provider(quotes_return=None, quotes_side_effect=None):
    """Create a mock PriceProvider with async batch_fetch_quotes stub."""
    provider = MagicMock()
    if quotes_side_effect is not None:
        provider.batch_fetch_quotes = AsyncMock(side_effect=quotes_side_effect)
    else:
        provider.batch_fetch_quotes = AsyncMock(return_value=quotes_return or [])
    return provider


async def test_get_quotes_parses_symbols():
    mock_quotes = [Quote(**{"symbol": "AAPL", "price": 185.50})]
    mock_prov = _mock_provider(quotes_return=mock_quotes)
    with patch("app.services.quote_service.get_price_provider", return_value=mock_prov):
        result = await get_quotes("AAPL,MSFT")
    assert result == mock_quotes


async def test_get_quotes_uppercase_normalization():
    mock_prov = _mock_provider(quotes_return=[])
    with patch("app.services.quote_service.get_price_provider", return_value=mock_prov):
        await get_quotes("aapl, msft")
    mock_prov.batch_fetch_quotes.assert_awaited_once_with(["AAPL", "MSFT"])


async def test_get_quotes_empty_returns_empty():
    result = await get_quotes("")
    assert result == []


# --- recent_sessions: the calendar half of session identity (#626, #642) -----

def test_attach_recent_sessions_skips_a_holiday():
    """Easter Monday's prior session is the Thursday — Good Friday isn't one.
    A naive "session_date minus one business day" would name the holiday and
    the client would then reject a perfectly good stored bar."""
    quotes = [Quote(symbol="AAPL", session_date="2025-04-21")]
    sessions = attach_recent_sessions(quotes)[0].recent_sessions
    assert sessions[:2] == ["2025-04-21", "2025-04-17"]


def test_attach_recent_sessions_skips_a_weekend():
    quotes = [Quote(symbol="AAPL", session_date="2025-04-14")]  # Monday
    assert attach_recent_sessions(quotes)[0].recent_sessions[:2] == ["2025-04-14", "2025-04-11"]


def test_attach_recent_sessions_is_newest_first_and_window_sized():
    """The client reads the distance off the index, so order and length are the
    contract, not incidental."""
    quotes = [Quote(symbol="AAPL", session_date="2025-04-21")]
    sessions = attach_recent_sessions(quotes)[0].recent_sessions
    assert len(sessions) == QUOTE_SESSION_WINDOW
    assert sessions == sorted(sessions, reverse=True)
    assert sessions[0] == "2025-04-21"


def test_window_covers_every_distance_the_client_will_accept():
    """The frontend scores a bar up to VNR_MAX_SESSIONS_BEHIND back. If the
    window were ever shorter, those bars would fall off the end and blank —
    silently undoing #642. Derived, so this asserts the derivation."""
    assert QUOTE_SESSION_WINDOW > VNR_MAX_SESSIONS_BEHIND


def test_attach_recent_sessions_handles_a_247_venue():
    """Crypto trades every day, so the sessions are simply consecutive."""
    quotes = [Quote(symbol="BTC-USD", session_date="2025-04-21")]
    sessions = attach_recent_sessions(quotes)[0].recent_sessions
    assert sessions[:3] == ["2025-04-21", "2025-04-20", "2025-04-19"]


def test_attach_recent_sessions_leaves_unknown_venues_null():
    """Fail-safe, as everywhere in market_calendar: no calendar, no answer —
    the client falls back rather than being handed a guess."""
    quotes = [Quote(symbol="FOO.ZZ", session_date="2025-04-21")]
    assert attach_recent_sessions(quotes)[0].recent_sessions is None


def test_attach_recent_sessions_tolerates_missing_or_bad_session_date():
    quotes = [
        Quote(symbol="AAPL"),                              # degraded quote
        Quote(symbol="MSFT", session_date="not-a-date"),   # provider garbage
    ]
    assert [q.recent_sessions for q in attach_recent_sessions(quotes)] == [None, None]


def test_attach_recent_sessions_resolves_once_per_calendar():
    """Dozens of tickers, a handful of venues: the calendar lookup is keyed by
    (calendar, session_date), not by symbol."""
    quotes = [Quote(symbol=s, session_date="2025-04-21") for s in ("AAPL", "MSFT", "IBM")]
    with patch("app.services.quote_service.AssetRef", wraps=AssetRef) as spy:
        out = attach_recent_sessions(quotes)
    assert {tuple(q.recent_sessions) for q in out} == {tuple(out[0].recent_sessions)}
    # One AssetRef per quote is fine; the point is the *calendar* query is shared.
    assert spy.call_count == 3


async def test_get_quotes_attaches_recent_sessions():
    """The REST path enriches too — it used to strip session_date entirely."""
    mock_prov = _mock_provider(quotes_return=[Quote(symbol="AAPL", session_date="2025-04-21")])
    with patch("app.services.quote_service.get_price_provider", return_value=mock_prov):
        result = await get_quotes("AAPL")
    assert result[0].session_date == "2025-04-21"
    assert result[0].recent_sessions[:2] == ["2025-04-21", "2025-04-17"]


async def test_stream_emits_full_payload_first():
    """First SSE event should contain all symbols (full payload)."""
    mock_quotes = [
        Quote(**{"symbol": "AAPL", "price": 185.50, "market_state": "REGULAR"}),
    ]

    call_count = 0
    async def mock_sleep(seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 1:
            raise asyncio.CancelledError()

    mock_session_ctx = AsyncMock()
    mock_db = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_prov = _mock_provider(quotes_return=mock_quotes)

    with (
        patch("app.services.quote_service.async_session", return_value=mock_session_ctx),
        patch("app.services.quote_service.AssetRepository") as MockRepo,
        patch("app.services.quote_service.get_price_provider", return_value=mock_prov),
        patch("app.services.quote_service.asyncio.sleep", side_effect=mock_sleep),
        patch("app.services.quote_service.get_intraday_bars", new_callable=AsyncMock, return_value={}),
    ):
        MockRepo.return_value.list_in_any_group_refs = AsyncMock(return_value=[AssetRef("AAPL", 1)])

        events = []
        async for event in quote_event_generator():
            events.append(event)

    quote_events = [e for e in events if e.startswith("event: quotes")]
    assert len(quote_events) >= 1
    data = json.loads(quote_events[0].split("data: ")[1].split("\n")[0])
    assert "AAPL" in data


async def test_stream_delta_only_changed():
    """After initial full payload, subsequent events only contain changed data."""
    quote_v1 = [
        Quote(**{"symbol": "AAPL", "price": 185.50, "market_state": "REGULAR"}),
        Quote(**{"symbol": "MSFT", "price": 420.00, "market_state": "REGULAR"}),
    ]
    quote_v2 = [
        Quote(**{"symbol": "AAPL", "price": 186.00, "market_state": "REGULAR"}),  # changed
        Quote(**{"symbol": "MSFT", "price": 420.00, "market_state": "REGULAR"}),  # unchanged
    ]

    call_count = 0
    async def mock_sleep(seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise asyncio.CancelledError()

    mock_session_ctx = AsyncMock()
    mock_db = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_prov = _mock_provider(quotes_side_effect=[quote_v1, quote_v2])

    with (
        patch("app.services.quote_service.async_session", return_value=mock_session_ctx),
        patch("app.services.quote_service.AssetRepository") as MockRepo,
        patch("app.services.quote_service.get_price_provider", return_value=mock_prov),
        patch("app.services.quote_service.asyncio.sleep", side_effect=mock_sleep),
        patch("app.services.quote_service.get_intraday_bars", new_callable=AsyncMock, return_value={}),
    ):
        MockRepo.return_value.list_in_any_group_refs = AsyncMock(return_value=[AssetRef("AAPL", 1), AssetRef("MSFT", 2)])

        events = []
        async for event in quote_event_generator():
            events.append(event)

    quote_events = [e for e in events if e.startswith("event: quotes")]
    assert len(quote_events) == 2
    # Second event should only contain AAPL (MSFT unchanged)
    data2 = json.loads(quote_events[1].split("data: ")[1].split("\n")[0])
    assert "AAPL" in data2
    assert "MSFT" not in data2


async def test_stream_intraday_event_serializes_bars():
    """The ``intraday`` SSE event carries {symbol: [bar]} with the wire keys
    time/price/volume/session (the frontend's ``IntradayPoint`` mirror).

    Note the explicit subscription: bars are opt-in, so this test has to ask
    for them the way a live view does.
    """
    mock_quotes = [Quote(**{"symbol": "AAPL", "price": 185.50, "market_state": "REGULAR"})]
    bars = {
        "AAPL": [
            IntradayBar(time=1771000000, price=185.5, volume=1200, session="regular"),
            IntradayBar(time=1771000060, price=185.6, volume=800, session="regular"),
        ]
    }

    async def mock_sleep(seconds):
        raise asyncio.CancelledError()

    mock_session_ctx = AsyncMock()
    mock_db = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_prov = _mock_provider(quotes_return=mock_quotes)

    with (
        patch("app.services.quote_service.async_session", return_value=mock_session_ctx),
        patch("app.services.quote_service.AssetRepository") as MockRepo,
        patch("app.services.quote_service.get_price_provider", return_value=mock_prov),
        patch("app.services.quote_service.asyncio.sleep", side_effect=mock_sleep),
        patch("app.services.quote_service.get_intraday_bars", new_callable=AsyncMock, return_value=bars),
    ):
        MockRepo.return_value.list_in_any_group_refs = AsyncMock(return_value=[AssetRef("AAPL", 1)])

        events = []
        async for event in quote_event_generator(frozenset({"AAPL"})):
            events.append(event)

    intraday_events = [e for e in events if e.startswith("event: intraday")]
    assert len(intraday_events) == 1
    data = json.loads(intraday_events[0].split("data: ")[1].split("\n")[0])
    assert data == {
        "AAPL": [
            {"time": 1771000000, "price": 185.5, "volume": 1200, "session": "regular"},
            {"time": 1771000060, "price": 185.6, "volume": 800, "session": "regular"},
        ]
    }


async def test_stream_without_subscription_sends_no_intraday():
    """No subscription means silence, not everything.

    The whole saving in #621 rests on this default: the board, the group table
    and every other view hold this stream without drawing a single bar, and
    used to be sent 738 KiB anyway.
    """
    mock_quotes = [Quote(**{"symbol": "AAPL", "price": 185.50, "market_state": "REGULAR"})]
    bars_call = AsyncMock(return_value={"AAPL": [
        IntradayBar(time=1771000000, price=185.5, volume=1200, session="regular"),
    ]})

    async def mock_sleep(seconds):
        raise asyncio.CancelledError()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.quote_service.async_session", return_value=mock_session_ctx),
        patch("app.services.quote_service.AssetRepository") as MockRepo,
        patch("app.services.quote_service.get_price_provider", return_value=_mock_provider(mock_quotes)),
        patch("app.services.quote_service.asyncio.sleep", side_effect=mock_sleep),
        patch("app.services.quote_service.get_intraday_bars", bars_call),
    ):
        MockRepo.return_value.list_in_any_group_refs = AsyncMock(return_value=[AssetRef("AAPL", 1)])

        events = [e async for e in quote_event_generator()]

    assert not [e for e in events if e.startswith("event: intraday")]
    # Not merely filtered out of the payload — never read from the DB.
    bars_call.assert_not_awaited()
    # Quotes still flow: this is scoping intraday, not muting the stream.
    assert [e for e in events if e.startswith("event: quotes")]


async def test_stream_intraday_scoped_to_subscribed_symbols():
    """A subscription for one symbol must not drag the rest of the roster along."""
    mock_quotes = [
        Quote(**{"symbol": "AAPL", "price": 185.50, "market_state": "REGULAR"}),
        Quote(**{"symbol": "MSFT", "price": 420.00, "market_state": "REGULAR"}),
    ]
    seen_refs: list[list[AssetRef]] = []

    async def capture_bars(db, refs):
        seen_refs.append(list(refs))
        return {}

    async def mock_sleep(seconds):
        raise asyncio.CancelledError()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.quote_service.async_session", return_value=mock_session_ctx),
        patch("app.services.quote_service.AssetRepository") as MockRepo,
        patch("app.services.quote_service.get_price_provider", return_value=_mock_provider(mock_quotes)),
        patch("app.services.quote_service.asyncio.sleep", side_effect=mock_sleep),
        patch("app.services.quote_service.get_intraday_bars", capture_bars),
    ):
        MockRepo.return_value.list_in_any_group_refs = AsyncMock(
            return_value=[AssetRef("AAPL", 1), AssetRef("MSFT", 2)]
        )

        async for _ in quote_event_generator(frozenset({"MSFT"})):
            pass

    assert seen_refs == [[AssetRef("MSFT", 2)]]


async def test_stream_adaptive_interval_regular():
    """During regular market hours, interval should be 15 seconds."""
    mock_quotes = [Quote(**{"symbol": "AAPL", "price": 185.50, "market_state": "REGULAR"})]

    sleep_intervals = []
    async def mock_sleep(seconds):
        sleep_intervals.append(seconds)
        raise asyncio.CancelledError()

    mock_session_ctx = AsyncMock()
    mock_db = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_prov = _mock_provider(quotes_return=mock_quotes)

    with (
        patch("app.services.quote_service.async_session", return_value=mock_session_ctx),
        patch("app.services.quote_service.AssetRepository") as MockRepo,
        patch("app.services.quote_service.get_price_provider", return_value=mock_prov),
        patch("app.services.quote_service.asyncio.sleep", side_effect=mock_sleep),
        patch("app.services.quote_service.get_intraday_bars", new_callable=AsyncMock, return_value={}),
        # Pin the venue schedule: the real hint is wall-clock dependent and
        # caps the sleep to "seconds until the next bell" near an open.
        patch("app.services.quote_service.schedule_poll_hint", return_value=("open", None)),
    ):
        MockRepo.return_value.list_in_any_group_refs = AsyncMock(return_value=[AssetRef("AAPL", 1)])
        async for _ in quote_event_generator():
            pass

    assert sleep_intervals[0] == 15


async def test_stream_adaptive_interval_closed():
    """When market is closed, interval should be 300 seconds."""
    mock_quotes = [Quote(**{"symbol": "AAPL", "price": 185.50, "market_state": "CLOSED"})]

    sleep_intervals = []
    async def mock_sleep(seconds):
        sleep_intervals.append(seconds)
        raise asyncio.CancelledError()

    mock_session_ctx = AsyncMock()
    mock_db = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_prov = _mock_provider(quotes_return=mock_quotes)

    with (
        patch("app.services.quote_service.async_session", return_value=mock_session_ctx),
        patch("app.services.quote_service.AssetRepository") as MockRepo,
        patch("app.services.quote_service.get_price_provider", return_value=mock_prov),
        patch("app.services.quote_service.asyncio.sleep", side_effect=mock_sleep),
        patch("app.services.quote_service.get_intraday_bars", new_callable=AsyncMock, return_value={}),
        # Pin the venue schedule: the real hint is wall-clock dependent and
        # caps the sleep to "seconds until the next bell" near an open —
        # this test failed for 5 real-world minutes before every NYSE open.
        patch("app.services.quote_service.schedule_poll_hint", return_value=("closed", None)),
    ):
        MockRepo.return_value.list_in_any_group_refs = AsyncMock(return_value=[AssetRef("AAPL", 1)])
        async for _ in quote_event_generator():
            pass

    assert sleep_intervals[0] == 300

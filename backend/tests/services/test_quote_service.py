"""Unit tests for quote_service — REST parsing, SSE delta compression, adaptive intervals."""

import asyncio
import json

import pytest
from unittest.mock import AsyncMock, patch

from app.services.quote_service import get_quotes, quote_event_generator

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_get_quotes_parses_symbols():
    mock_quotes = [{"symbol": "AAPL", "price": 185.50}]
    with patch("app.services.quote_service.batch_fetch_quotes", new_callable=AsyncMock, return_value=mock_quotes):
        result = await get_quotes("AAPL,MSFT")
    assert result == mock_quotes


async def test_get_quotes_uppercase_normalization():
    with patch("app.services.quote_service.batch_fetch_quotes", new_callable=AsyncMock, return_value=[]) as mock:
        await get_quotes("aapl, msft")
    mock.assert_awaited_once_with(["AAPL", "MSFT"])


async def test_get_quotes_empty_returns_empty():
    result = await get_quotes("")
    assert result == []


async def test_stream_emits_full_payload_first():
    """First SSE event should contain all symbols (full payload)."""
    mock_quotes = [
        {"symbol": "AAPL", "price": 185.50, "market_state": "REGULAR"},
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

    with (
        patch("app.services.quote_service.async_session", return_value=mock_session_ctx),
        patch("app.services.quote_service.AssetRepository") as MockRepo,
        patch("app.services.quote_service.batch_fetch_quotes", new_callable=AsyncMock, return_value=mock_quotes),
        patch("app.services.quote_service.asyncio.sleep", side_effect=mock_sleep),
        patch("app.services.quote_service.get_intraday_bars", new_callable=AsyncMock, return_value={}),
    ):
        MockRepo.return_value.list_in_any_group_id_symbol_pairs = AsyncMock(return_value=[(1, "AAPL")])

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
        {"symbol": "AAPL", "price": 185.50, "market_state": "REGULAR"},
        {"symbol": "MSFT", "price": 420.00, "market_state": "REGULAR"},
    ]
    quote_v2 = [
        {"symbol": "AAPL", "price": 186.00, "market_state": "REGULAR"},  # changed
        {"symbol": "MSFT", "price": 420.00, "market_state": "REGULAR"},  # unchanged
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

    with (
        patch("app.services.quote_service.async_session", return_value=mock_session_ctx),
        patch("app.services.quote_service.AssetRepository") as MockRepo,
        patch("app.services.quote_service.batch_fetch_quotes", new_callable=AsyncMock, side_effect=[quote_v1, quote_v2]),
        patch("app.services.quote_service.asyncio.sleep", side_effect=mock_sleep),
        patch("app.services.quote_service.get_intraday_bars", new_callable=AsyncMock, return_value={}),
    ):
        MockRepo.return_value.list_in_any_group_id_symbol_pairs = AsyncMock(return_value=[(1, "AAPL"), (2, "MSFT")])

        events = []
        async for event in quote_event_generator():
            events.append(event)

    quote_events = [e for e in events if e.startswith("event: quotes")]
    assert len(quote_events) == 2
    # Second event should only contain AAPL (MSFT unchanged)
    data2 = json.loads(quote_events[1].split("data: ")[1].split("\n")[0])
    assert "AAPL" in data2
    assert "MSFT" not in data2


async def test_stream_adaptive_interval_regular():
    """During regular market hours, interval should be 15 seconds."""
    mock_quotes = [{"symbol": "AAPL", "price": 185.50, "market_state": "REGULAR"}]

    sleep_intervals = []
    async def mock_sleep(seconds):
        sleep_intervals.append(seconds)
        raise asyncio.CancelledError()

    mock_session_ctx = AsyncMock()
    mock_db = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.quote_service.async_session", return_value=mock_session_ctx),
        patch("app.services.quote_service.AssetRepository") as MockRepo,
        patch("app.services.quote_service.batch_fetch_quotes", new_callable=AsyncMock, return_value=mock_quotes),
        patch("app.services.quote_service.asyncio.sleep", side_effect=mock_sleep),
        patch("app.services.quote_service.get_intraday_bars", new_callable=AsyncMock, return_value={}),
    ):
        MockRepo.return_value.list_in_any_group_id_symbol_pairs = AsyncMock(return_value=[(1, "AAPL")])
        async for _ in quote_event_generator():
            pass

    assert sleep_intervals[0] == 15


async def test_stream_adaptive_interval_closed():
    """When market is closed, interval should be 300 seconds."""
    mock_quotes = [{"symbol": "AAPL", "price": 185.50, "market_state": "CLOSED"}]

    sleep_intervals = []
    async def mock_sleep(seconds):
        sleep_intervals.append(seconds)
        raise asyncio.CancelledError()

    mock_session_ctx = AsyncMock()
    mock_db = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.quote_service.async_session", return_value=mock_session_ctx),
        patch("app.services.quote_service.AssetRepository") as MockRepo,
        patch("app.services.quote_service.batch_fetch_quotes", new_callable=AsyncMock, return_value=mock_quotes),
        patch("app.services.quote_service.asyncio.sleep", side_effect=mock_sleep),
        patch("app.services.quote_service.get_intraday_bars", new_callable=AsyncMock, return_value={}),
    ):
        MockRepo.return_value.list_in_any_group_id_symbol_pairs = AsyncMock(return_value=[(1, "AAPL")])
        async for _ in quote_event_generator():
            pass

    assert sleep_intervals[0] == 300

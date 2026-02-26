"""Tests for the quotes router (REST + SSE stream)."""

import asyncio
import json

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.quote_service import _reset_asset_list_cache
from tests.conftest import TestSession

pytestmark = pytest.mark.asyncio(loop_scope="function")


_MOCK_QUOTES = [
    {
        "symbol": "AAPL",
        "price": 185.50,
        "previous_close": 184.00,
        "change": 1.50,
        "change_percent": 0.82,
        "currency": "USD",
        "market_state": "REGULAR",
    },
    {
        "symbol": "MSFT",
        "price": 420.00,
        "previous_close": 418.50,
        "change": 1.50,
        "change_percent": 0.36,
        "currency": "USD",
        "market_state": "REGULAR",
    },
]


def _parse_sse_events(body: str) -> list[dict]:
    """Parse SSE text into a list of data payloads."""
    events = []
    for line in body.split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _mock_provider(quotes_return=None, quotes_side_effect=None):
    """Create a mock PriceProvider with batch_fetch_quotes stub."""
    provider = MagicMock()
    if quotes_side_effect is not None:
        provider.batch_fetch_quotes = AsyncMock(side_effect=quotes_side_effect)
    else:
        provider.batch_fetch_quotes = AsyncMock(return_value=quotes_return or [])
    return provider


# ── REST endpoint tests ──────────────────────────────────────────────


async def test_get_quotes_returns_data(client):
    """GET /api/quotes returns quote data for requested symbols."""
    mock_prov = _mock_provider(quotes_return=_MOCK_QUOTES)
    with patch("app.services.quote_service.get_price_provider", return_value=mock_prov):
        resp = await client.get("/api/quotes", params={"symbols": "AAPL,MSFT"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["symbol"] == "AAPL"
    assert data[0]["price"] == 185.50
    assert data[1]["symbol"] == "MSFT"


async def test_get_quotes_empty_symbols(client):
    """GET /api/quotes with empty symbols returns empty list."""
    mock_prov = _mock_provider(quotes_return=[])
    with patch("app.services.quote_service.get_price_provider", return_value=mock_prov):
        resp = await client.get("/api/quotes", params={"symbols": ""})

    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_quotes_single_symbol(client):
    """GET /api/quotes works with a single symbol."""
    mock_prov = _mock_provider(quotes_return=[_MOCK_QUOTES[0]])
    with patch("app.services.quote_service.get_price_provider", return_value=mock_prov):
        resp = await client.get("/api/quotes", params={"symbols": "AAPL"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"
    assert data[0]["market_state"] == "REGULAR"
    assert data[0]["currency"] == "USD"


async def test_get_quotes_uppercase_normalization(client):
    """Symbols are normalized to uppercase before fetching."""
    mock_prov = _mock_provider(quotes_return=[_MOCK_QUOTES[0]])
    with patch("app.services.quote_service.get_price_provider", return_value=mock_prov):
        await client.get("/api/quotes", params={"symbols": "aapl"})

    mock_prov.batch_fetch_quotes.assert_awaited_once_with(["AAPL"])


# ── SSE stream tests ─────────────────────────────────────────────────
# The SSE generator uses async_session directly (not get_db), so we must
# patch it to use the test database session.


async def test_stream_quotes_no_tracked(client):
    """SSE stream emits empty payload when no assets are tracked."""
    _reset_asset_list_cache()
    with (
        patch("app.services.quote_service.async_session", TestSession),
        patch("app.services.quote_service.asyncio.sleep", side_effect=asyncio.CancelledError()),
    ):
        resp = await client.get("/api/quotes/stream")

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "event: quotes" in body
    assert "data: {}" in body


async def test_stream_quotes_emits_event(client):
    """SSE stream emits quote data for tracked assets."""
    await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple", "type": "stock"})

    _reset_asset_list_cache()
    mock_prov = _mock_provider(quotes_return=[_MOCK_QUOTES[0]])
    with (
        patch("app.services.quote_service.async_session", TestSession),
        patch("app.services.quote_service.get_price_provider", return_value=mock_prov),
        patch("app.services.quote_service.asyncio.sleep", side_effect=asyncio.CancelledError()),
    ):
        resp = await client.get("/api/quotes/stream")

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    assert len(events) >= 1
    assert "AAPL" in events[0]
    assert events[0]["AAPL"]["price"] == 185.50
    assert events[0]["AAPL"]["market_state"] == "REGULAR"


async def test_stream_quotes_cache_headers(client):
    """SSE stream sets correct cache-control and buffering headers."""
    _reset_asset_list_cache()
    with (
        patch("app.services.quote_service.async_session", TestSession),
        patch("app.services.quote_service.asyncio.sleep", side_effect=asyncio.CancelledError()),
    ):
        resp = await client.get("/api/quotes/stream")

    assert resp.headers.get("cache-control") == "no-cache"
    assert resp.headers.get("x-accel-buffering") == "no"


async def test_stream_quotes_multiple_symbols(client):
    """SSE stream includes all tracked symbols in first event."""
    await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple", "type": "stock"})
    await client.post("/api/assets", json={"symbol": "MSFT", "name": "Microsoft", "type": "stock"})

    _reset_asset_list_cache()
    mock_prov = _mock_provider(quotes_return=_MOCK_QUOTES)
    with (
        patch("app.services.quote_service.async_session", TestSession),
        patch("app.services.quote_service.get_price_provider", return_value=mock_prov),
        patch("app.services.quote_service.asyncio.sleep", side_effect=asyncio.CancelledError()),
    ):
        resp = await client.get("/api/quotes/stream")

    events = _parse_sse_events(resp.text)
    assert len(events) >= 1
    assert "AAPL" in events[0]
    assert "MSFT" in events[0]

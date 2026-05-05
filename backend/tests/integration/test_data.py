"""Tests for GET /api/data batch query endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import make_yahoo_df, seed_asset_with_prices

pytestmark = pytest.mark.asyncio(loop_scope="function")


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


async def test_missing_symbols_422(client):
    resp = await client.get("/api/data")
    assert resp.status_code == 422


async def test_empty_symbols_422(client):
    resp = await client.get("/api/data?symbols=")
    assert resp.status_code == 422


async def test_too_many_symbols_422(client):
    syms = ",".join(f"SYM{i}" for i in range(51))
    resp = await client.get(f"/api/data?symbols={syms}")
    assert resp.status_code == 422
    assert "50" in resp.json()["detail"]


async def test_invalid_field_422(client):
    resp = await client.get("/api/data?symbols=AAPL&fields=bogus")
    assert resp.status_code == 422
    assert "bogus" in resp.json()["detail"]


async def test_invalid_period_422(client):
    resp = await client.get("/api/data?symbols=AAPL&fields=quote&period=99y")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Quote field
# ---------------------------------------------------------------------------


async def test_quote_field(client):
    mock_quotes = [{"symbol": "AAPL", "price": 185.50, "change": 1.2}]
    mock_prov = MagicMock()
    mock_prov.batch_fetch_quotes = AsyncMock(return_value=mock_quotes)
    with patch("app.services.data_service.get_price_provider", return_value=mock_prov):
        resp = await client.get("/api/data?symbols=AAPL&fields=quote")
    assert resp.status_code == 200
    data = resp.json()
    assert "AAPL" in data
    assert "quote" in data["AAPL"]
    assert data["AAPL"]["quote"]["price"] == 185.50


async def test_quote_multiple_symbols(client):
    mock_quotes = [
        {"symbol": "AAPL", "price": 185.50},
        {"symbol": "MSFT", "price": 420.00},
    ]
    mock_prov = MagicMock()
    mock_prov.batch_fetch_quotes = AsyncMock(return_value=mock_quotes)
    with patch("app.services.data_service.get_price_provider", return_value=mock_prov):
        resp = await client.get("/api/data?symbols=AAPL,MSFT&fields=quote")
    assert resp.status_code == 200
    data = resp.json()
    assert "AAPL" in data
    assert "MSFT" in data
    assert data["AAPL"]["quote"]["price"] == 185.50
    assert data["MSFT"]["quote"]["price"] == 420.00


# ---------------------------------------------------------------------------
# Snapshot field
# ---------------------------------------------------------------------------


async def test_snapshot_field(client):
    mock_snapshots = [
        {"symbol": "AAPL", "close": 185.5, "change_pct": 0.65, "currency": "USD", "values": {"rsi": 62.3}},
    ]
    with patch("app.services.data_service.compute_batch_indicator_snapshots", new_callable=AsyncMock, return_value=mock_snapshots):
        resp = await client.get("/api/data?symbols=AAPL&fields=snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "AAPL" in data
    assert "snapshot" in data["AAPL"]
    assert data["AAPL"]["snapshot"]["close"] == 185.5
    # symbol key should be removed from the snapshot data
    assert "symbol" not in data["AAPL"]["snapshot"]


# ---------------------------------------------------------------------------
# Prices field
# ---------------------------------------------------------------------------


async def test_prices_tracked_asset(client, db):
    """Tracked assets return prices from DB."""
    await seed_asset_with_prices(db, symbol="TEST")
    resp = await client.get("/api/data?symbols=TEST&fields=prices&period=3mo")
    assert resp.status_code == 200
    data = resp.json()
    assert "TEST" in data
    assert "prices" in data["TEST"]
    assert len(data["TEST"]["prices"]) > 0
    assert set(data["TEST"]["prices"][0].keys()) == {"date", "open", "high", "low", "close", "volume"}


async def test_prices_untracked_ephemeral(client):
    """Untracked symbols fetch prices ephemerally from the provider."""
    mock_df = make_yahoo_df()
    mock_prov = MagicMock()
    mock_prov.fetch_history = AsyncMock(return_value=mock_df)
    with patch("app.services.price_service.get_price_provider", return_value=mock_prov):
        resp = await client.get("/api/data?symbols=UNKNOWN&fields=prices&period=3mo")
    assert resp.status_code == 200
    data = resp.json()
    assert "UNKNOWN" in data
    assert "prices" in data["UNKNOWN"]
    assert len(data["UNKNOWN"]["prices"]) > 0


# ---------------------------------------------------------------------------
# Indicators field
# ---------------------------------------------------------------------------


async def test_indicators_tracked_asset(client, db):
    """Tracked assets return computed indicators from DB prices."""
    await seed_asset_with_prices(db, symbol="TEST")
    resp = await client.get("/api/data?symbols=TEST&fields=indicators&period=3mo")
    assert resp.status_code == 200
    data = resp.json()
    assert "TEST" in data
    assert "indicators" in data["TEST"]
    assert len(data["TEST"]["indicators"]) > 0
    row = data["TEST"]["indicators"][0]
    assert "date" in row
    assert "close" in row
    assert "values" in row


# ---------------------------------------------------------------------------
# Default fields (quote + snapshot)
# ---------------------------------------------------------------------------


async def test_default_fields(client):
    """Omitting fields parameter returns quote + snapshot."""
    mock_quotes = [{"symbol": "AAPL", "price": 185.50}]
    mock_snapshots = [{"symbol": "AAPL", "close": 185.5, "values": {"rsi": 55.0}}]
    mock_prov = MagicMock()
    mock_prov.batch_fetch_quotes = AsyncMock(return_value=mock_quotes)
    with (
        patch("app.services.data_service.get_price_provider", return_value=mock_prov),
        patch("app.services.data_service.compute_batch_indicator_snapshots", new_callable=AsyncMock, return_value=mock_snapshots),
    ):
        resp = await client.get("/api/data?symbols=AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert "AAPL" in data
    assert "quote" in data["AAPL"]
    assert "snapshot" in data["AAPL"]


# ---------------------------------------------------------------------------
# All fields combined
# ---------------------------------------------------------------------------


async def test_all_fields(client, db):
    await seed_asset_with_prices(db, symbol="TEST")
    mock_quotes = [{"symbol": "TEST", "price": 150.0}]
    mock_snapshots = [{"symbol": "TEST", "close": 150.0, "values": {"rsi": 55.0}}]
    mock_prov = MagicMock()
    mock_prov.batch_fetch_quotes = AsyncMock(return_value=mock_quotes)
    with (
        patch("app.services.data_service.get_price_provider", return_value=mock_prov),
        patch("app.services.data_service.compute_batch_indicator_snapshots", new_callable=AsyncMock, return_value=mock_snapshots),
    ):
        resp = await client.get("/api/data?symbols=TEST&fields=quote,snapshot,prices,indicators&period=3mo")
    assert resp.status_code == 200
    data = resp.json()
    assert "TEST" in data
    assert "quote" in data["TEST"]
    assert "snapshot" in data["TEST"]
    assert "prices" in data["TEST"]
    assert "indicators" in data["TEST"]


# ---------------------------------------------------------------------------
# Symbol handling
# ---------------------------------------------------------------------------


async def test_symbols_uppercase_normalization(client):
    mock_quotes = [{"symbol": "AAPL", "price": 185.50}]
    mock_prov = MagicMock()
    mock_prov.batch_fetch_quotes = AsyncMock(return_value=mock_quotes)
    with patch("app.services.data_service.get_price_provider", return_value=mock_prov):
        resp = await client.get("/api/data?symbols=aapl&fields=quote")
    assert resp.status_code == 200
    data = resp.json()
    assert "AAPL" in data


async def test_invalid_symbol_returns_error_not_500(client):
    """Invalid symbols get a per-symbol error, not a 500."""
    mock_prov = MagicMock()
    mock_prov.batch_fetch_quotes = AsyncMock(return_value=[])
    mock_prov.fetch_history = AsyncMock(side_effect=ValueError("No data"))
    with (
        patch("app.services.data_service.get_price_provider", return_value=mock_prov),
        patch("app.services.price_service.get_price_provider", return_value=mock_prov),
    ):
        resp = await client.get("/api/data?symbols=BADTICKER&fields=quote,prices")
    assert resp.status_code == 200
    data = resp.json()
    assert "BADTICKER" in data
    # quote was empty (not in batch result) and prices failed
    assert "error" in data["BADTICKER"]


async def test_mixed_tracked_untracked(client, db):
    """Request with both tracked and untracked symbols returns data for both."""
    await seed_asset_with_prices(db, symbol="TRACKED")
    mock_quotes = [
        {"symbol": "TRACKED", "price": 150.0},
        {"symbol": "UNTRACKED", "price": 200.0},
    ]
    mock_df = make_yahoo_df()
    mock_prov = MagicMock()
    mock_prov.batch_fetch_quotes = AsyncMock(return_value=mock_quotes)
    mock_prov.fetch_history = AsyncMock(return_value=mock_df)
    with (
        patch("app.services.data_service.get_price_provider", return_value=mock_prov),
        patch("app.services.price_service.get_price_provider", return_value=mock_prov),
    ):
        resp = await client.get("/api/data?symbols=TRACKED,UNTRACKED&fields=quote,prices&period=3mo")
    assert resp.status_code == 200
    data = resp.json()
    assert "TRACKED" in data
    assert "UNTRACKED" in data
    assert "quote" in data["TRACKED"]
    assert "prices" in data["TRACKED"]
    assert "prices" in data["UNTRACKED"]


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


async def test_response_only_requested_fields(client):
    """Response should only contain the fields that were requested."""
    mock_quotes = [{"symbol": "AAPL", "price": 185.50}]
    mock_prov = MagicMock()
    mock_prov.batch_fetch_quotes = AsyncMock(return_value=mock_quotes)
    with patch("app.services.data_service.get_price_provider", return_value=mock_prov):
        resp = await client.get("/api/data?symbols=AAPL&fields=quote")
    data = resp.json()
    assert "quote" in data["AAPL"]
    # These fields were not requested, so they should not be present
    assert "snapshot" not in data["AAPL"]
    assert "prices" not in data["AAPL"]
    assert "indicators" not in data["AAPL"]


async def test_period_applied_to_prices(client, db):
    """Period param affects the date range of returned prices."""
    await seed_asset_with_prices(db, symbol="TEST")
    resp_3mo = await client.get("/api/data?symbols=TEST&fields=prices&period=3mo")
    resp_1y = await client.get("/api/data?symbols=TEST&fields=prices&period=1y")
    prices_3mo = resp_3mo.json()["TEST"]["prices"]
    prices_1y = resp_1y.json()["TEST"]["prices"]
    assert len(prices_1y) > len(prices_3mo)

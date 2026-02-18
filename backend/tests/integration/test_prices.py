"""Tests for the prices router (GET /prices, GET /indicators, POST /refresh)."""

import pytest
from datetime import date, timedelta
from unittest.mock import patch, AsyncMock

from tests.helpers import make_yahoo_df, seed_asset_with_prices

pytestmark = pytest.mark.asyncio(loop_scope="function")


# --- GET /prices ---

async def test_get_prices_returns_data(client, db):
    asset = await seed_asset_with_prices(db)
    resp = await client.get(f"/api/assets/{asset.symbol}/prices?period=3mo")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert set(data[0].keys()) == {"date", "open", "high", "low", "close", "volume"}


async def test_get_prices_period_filtering(client, db):
    """1y returns more data points than 3mo."""
    asset = await seed_asset_with_prices(db)
    resp_3mo = await client.get(f"/api/assets/{asset.symbol}/prices?period=3mo")
    resp_1y = await client.get(f"/api/assets/{asset.symbol}/prices?period=1y")
    assert len(resp_1y.json()) > len(resp_3mo.json())


async def test_get_prices_respects_period_boundary(client, db):
    """All returned dates fall within the requested period."""
    asset = await seed_asset_with_prices(db)
    resp = await client.get(f"/api/assets/{asset.symbol}/prices?period=3mo")
    cutoff = date.today() - timedelta(days=90)
    for row in resp.json():
        assert date.fromisoformat(row["date"]) >= cutoff


async def test_get_prices_ephemeral_symbol(client):
    """Untracked symbol fetches from Yahoo without persisting."""
    mock_df = make_yahoo_df()
    with patch("app.services.price_service.fetch_history", return_value=mock_df):
        resp = await client.get("/api/assets/UNKNOWN/prices?period=3mo")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


async def test_get_prices_unknown_404(client):
    """Symbol that fails Yahoo fetch returns 404."""
    with patch("app.services.price_service.fetch_history", side_effect=ValueError("No data")):
        resp = await client.get("/api/assets/XXXX/prices")
    assert resp.status_code == 404


# --- GET /indicators ---

async def test_get_indicators_fields(client, db):
    """Indicators endpoint returns all expected technical indicator fields."""
    asset = await seed_asset_with_prices(db)
    resp = await client.get(f"/api/assets/{asset.symbol}/indicators?period=3mo")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    expected = {"date", "close", "rsi", "sma_20", "sma_50",
                "bb_upper", "bb_middle", "bb_lower",
                "macd", "macd_signal", "macd_hist"}
    assert set(data[0].keys()) == expected


async def test_get_indicators_ephemeral(client):
    """Indicators for non-DB symbol uses ephemeral fetch with warmup."""
    mock_df = make_yahoo_df(n_days=120)
    with patch("app.services.price_service.fetch_history", return_value=mock_df):
        resp = await client.get("/api/assets/UNKNOWN/indicators?period=3mo")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


# --- POST /refresh ---

async def test_refresh_prices(client, db):
    """Refresh triggers sync and returns count."""
    asset = await seed_asset_with_prices(db, n_days=30)
    with patch("app.services.price_service.sync_asset_prices", new_callable=AsyncMock, return_value=42):
        resp = await client.post(f"/api/assets/{asset.symbol}/refresh?period=3mo")
    assert resp.status_code == 200
    assert resp.json() == {"symbol": asset.symbol, "synced": 42}


async def test_refresh_nonexistent_404(client):
    resp = await client.post("/api/assets/NOPE/refresh")
    assert resp.status_code == 404

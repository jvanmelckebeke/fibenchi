"""Tests for the prices router (GET /prices, GET /indicators, POST /refresh)."""

import pytest
from datetime import date, timedelta
from unittest.mock import patch, AsyncMock

import pandas as pd

from app.models import Asset, AssetType, PriceHistory

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _seed_asset_with_prices(db, symbol="AAPL", n_days=500, base_price=150.0):
    """Create a watchlisted asset with n_days of realistic price data."""
    asset = Asset(
        symbol=symbol, name=f"{symbol} Inc.",
        type=AssetType.STOCK, currency="USD", watchlisted=True,
    )
    db.add(asset)
    await db.flush()

    today = date.today()
    for i in range(n_days):
        d = today - timedelta(days=n_days - 1 - i)
        if d.weekday() >= 5:
            continue
        price = base_price + i * 0.1
        db.add(PriceHistory(
            asset_id=asset.id, date=d,
            open=round(price - 0.5, 4), high=round(price + 1.0, 4),
            low=round(price - 1.0, 4), close=round(price, 4),
            volume=1_000_000 + i * 1000,
        ))
    await db.commit()
    return asset


def _make_yahoo_df(n_days=60, base_price=100.0):
    """Create a DataFrame that looks like Yahoo Finance output."""
    dates = pd.bdate_range(end=date.today(), periods=n_days)
    prices = [base_price + i * 0.5 for i in range(n_days)]
    return pd.DataFrame({
        "open": [p - 0.5 for p in prices],
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": prices,
        "volume": [1_000_000] * n_days,
    }, index=dates)


# --- GET /prices ---

async def test_get_prices_returns_data(client, db):
    asset = await _seed_asset_with_prices(db)
    resp = await client.get(f"/api/assets/{asset.symbol}/prices?period=3mo")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert set(data[0].keys()) == {"date", "open", "high", "low", "close", "volume"}


async def test_get_prices_period_filtering(client, db):
    """1y returns more data points than 3mo."""
    asset = await _seed_asset_with_prices(db)
    resp_3mo = await client.get(f"/api/assets/{asset.symbol}/prices?period=3mo")
    resp_1y = await client.get(f"/api/assets/{asset.symbol}/prices?period=1y")
    assert len(resp_1y.json()) > len(resp_3mo.json())


async def test_get_prices_respects_period_boundary(client, db):
    """All returned dates fall within the requested period."""
    asset = await _seed_asset_with_prices(db)
    resp = await client.get(f"/api/assets/{asset.symbol}/prices?period=3mo")
    cutoff = date.today() - timedelta(days=90)
    for row in resp.json():
        assert date.fromisoformat(row["date"]) >= cutoff


async def test_get_prices_ephemeral_symbol(client):
    """Non-watchlisted symbol fetches from Yahoo without persisting."""
    mock_df = _make_yahoo_df()
    with patch("app.routers.prices.fetch_history", return_value=mock_df):
        resp = await client.get("/api/assets/UNKNOWN/prices?period=3mo")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


async def test_get_prices_unknown_404(client):
    """Symbol that fails Yahoo fetch returns 404."""
    with patch("app.routers.prices.fetch_history", side_effect=ValueError("No data")):
        resp = await client.get("/api/assets/XXXX/prices")
    assert resp.status_code == 404


# --- GET /indicators ---

async def test_get_indicators_fields(client, db):
    """Indicators endpoint returns all expected technical indicator fields."""
    asset = await _seed_asset_with_prices(db)
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
    mock_df = _make_yahoo_df(n_days=120)
    with patch("app.routers.prices.fetch_history", return_value=mock_df):
        resp = await client.get("/api/assets/UNKNOWN/indicators?period=3mo")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


# --- POST /refresh ---

async def test_refresh_prices(client, db):
    """Refresh triggers sync and returns count."""
    asset = await _seed_asset_with_prices(db, n_days=30)
    with patch("app.routers.prices.sync_asset_prices", new_callable=AsyncMock, return_value=42):
        resp = await client.post(f"/api/assets/{asset.symbol}/refresh?period=3mo")
    assert resp.status_code == 200
    assert resp.json() == {"symbol": asset.symbol, "synced": 42}


async def test_refresh_nonexistent_404(client):
    resp = await client.post("/api/assets/NOPE/refresh")
    assert resp.status_code == 404

"""Tests for batch watchlist endpoints (GET /watchlist/sparklines, GET /watchlist/indicators)."""

import pytest
from datetime import date, timedelta

from app.models import Asset, AssetType, PriceHistory

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _seed_assets(db, count=3, n_days=200):
    """Create multiple watchlisted assets with price history."""
    symbols = ["AAPL", "GOOGL", "MSFT"][:count]
    assets = []
    for i, sym in enumerate(symbols):
        asset = Asset(
            symbol=sym, name=f"{sym} Inc.",
            type=AssetType.STOCK, currency="USD", watchlisted=True,
        )
        db.add(asset)
        await db.flush()

        today = date.today()
        base_price = 100.0 + i * 50
        for j in range(n_days):
            d = today - timedelta(days=n_days - 1 - j)
            if d.weekday() >= 5:
                continue
            price = base_price + j * 0.1
            db.add(PriceHistory(
                asset_id=asset.id, date=d,
                open=round(price - 0.5, 4), high=round(price + 1.0, 4),
                low=round(price - 1.0, 4), close=round(price, 4),
                volume=1_000_000 + j * 1000,
            ))
        assets.append(asset)
    await db.commit()
    return assets


# --- GET /watchlist/sparklines ---

async def test_sparklines_returns_all_symbols(client, db):
    assets = await _seed_assets(db, count=3)
    resp = await client.get("/api/watchlist/sparklines?period=3mo")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"AAPL", "GOOGL", "MSFT"}


async def test_sparklines_close_only_fields(client, db):
    await _seed_assets(db, count=1)
    resp = await client.get("/api/watchlist/sparklines?period=3mo")
    data = resp.json()
    points = data["AAPL"]
    assert len(points) > 0
    assert set(points[0].keys()) == {"date", "close"}


async def test_sparklines_respects_period(client, db):
    await _seed_assets(db, count=1)
    resp_3mo = await client.get("/api/watchlist/sparklines?period=3mo")
    resp_1y = await client.get("/api/watchlist/sparklines?period=1y")
    assert len(resp_1y.json()["AAPL"]) > len(resp_3mo.json()["AAPL"])


async def test_sparklines_empty_watchlist(client, db):
    resp = await client.get("/api/watchlist/sparklines")
    assert resp.status_code == 200
    assert resp.json() == {}


async def test_sparklines_excludes_unwatchlisted(client, db):
    assets = await _seed_assets(db, count=2)
    # Unwatchlist one
    assets[1].watchlisted = False
    await db.commit()
    resp = await client.get("/api/watchlist/sparklines")
    data = resp.json()
    assert "AAPL" in data
    assert "GOOGL" not in data


# --- GET /watchlist/indicators ---

async def test_indicators_returns_all_symbols(client, db):
    assets = await _seed_assets(db, count=3)
    resp = await client.get("/api/watchlist/indicators")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"AAPL", "GOOGL", "MSFT"}


async def test_indicators_has_expected_fields(client, db):
    await _seed_assets(db, count=1)
    resp = await client.get("/api/watchlist/indicators")
    data = resp.json()
    ind = data["AAPL"]
    assert set(ind.keys()) == {"rsi", "macd", "macd_signal", "macd_hist"}


async def test_indicators_values_not_null_with_enough_data(client, db):
    await _seed_assets(db, count=1, n_days=200)
    resp = await client.get("/api/watchlist/indicators")
    data = resp.json()
    ind = data["AAPL"]
    assert ind["rsi"] is not None
    assert ind["macd"] is not None
    assert ind["macd_signal"] is not None
    assert ind["macd_hist"] is not None


async def test_indicators_null_with_insufficient_data(client, db):
    """With very few data points, indicators should be null."""
    asset = Asset(
        symbol="TINY", name="Tiny Inc.",
        type=AssetType.STOCK, currency="USD", watchlisted=True,
    )
    db.add(asset)
    await db.flush()
    # Only 5 days of data — not enough for any indicator
    today = date.today()
    for i in range(5):
        d = today - timedelta(days=4 - i)
        db.add(PriceHistory(
            asset_id=asset.id, date=d,
            open=100.0, high=101.0, low=99.0, close=100.0, volume=1000,
        ))
    await db.commit()

    resp = await client.get("/api/watchlist/indicators")
    data = resp.json()
    ind = data["TINY"]
    assert ind["rsi"] is None
    assert ind["macd"] is None


async def test_indicators_empty_watchlist(client, db):
    resp = await client.get("/api/watchlist/indicators")
    assert resp.status_code == 200
    assert resp.json() == {}

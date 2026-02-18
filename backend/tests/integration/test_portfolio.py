"""Tests for the portfolio router (GET /portfolio/index, GET /portfolio/performers)."""

import pytest

from tests.helpers import seed_asset_with_prices

pytestmark = pytest.mark.asyncio(loop_scope="function")


# --- GET /portfolio/index ---

async def test_index_empty_portfolio(client):
    """Empty portfolio returns zero values."""
    resp = await client.get("/api/portfolio/index?period=1y")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dates"] == []
    assert data["values"] == []
    assert data["current"] == 0
    assert data["change"] == 0
    assert data["change_pct"] == 0


async def test_index_returns_data(client, db):
    """Portfolio index with seeded assets returns dates/values."""
    await seed_asset_with_prices(db, symbol="AAPL", name="Apple", base_price=150.0, n_days=400)
    await seed_asset_with_prices(db, symbol="MSFT", name="Microsoft", base_price=300.0, n_days=400)

    resp = await client.get("/api/portfolio/index?period=1y")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["dates"]) > 0
    assert len(data["values"]) == len(data["dates"])
    assert data["current"] > 0


async def test_index_starts_at_base_value(client, db):
    """First value of the index should be close to the 1000 base value."""
    await seed_asset_with_prices(db, symbol="AAPL", name="Apple", base_price=150.0, n_days=400)

    resp = await client.get("/api/portfolio/index?period=1y")
    data = resp.json()
    assert len(data["values"]) > 0
    # First value should be the base_value (1000) or close to it
    assert abs(data["values"][0] - 1000.0) < 1.0


async def test_index_period_affects_length(client, db):
    """Shorter period returns fewer data points."""
    await seed_asset_with_prices(db, symbol="AAPL", name="Apple", base_price=150.0, n_days=400)

    resp_3mo = await client.get("/api/portfolio/index?period=3mo")
    resp_1y = await client.get("/api/portfolio/index?period=1y")
    assert len(resp_1y.json()["dates"]) > len(resp_3mo.json()["dates"])


# --- GET /portfolio/performers ---

async def test_performers_empty(client):
    resp = await client.get("/api/portfolio/performers?period=1y")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_performers_sorted_descending(client, db):
    """Performers are returned sorted by change_pct descending."""
    # AAPL: rising from 150 (+0.1/day) → positive return
    # MSFT: rising from 300 (+0.1/day) → smaller pct return (same absolute, higher base)
    await seed_asset_with_prices(db, symbol="AAPL", name="Apple", base_price=150.0, n_days=400)
    await seed_asset_with_prices(db, symbol="MSFT", name="Microsoft", base_price=300.0, n_days=400)

    resp = await client.get("/api/portfolio/performers?period=1y")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # AAPL should have higher pct return (same absolute gain, lower base)
    assert data[0]["symbol"] == "AAPL"
    assert data[1]["symbol"] == "MSFT"
    assert data[0]["change_pct"] > data[1]["change_pct"]


async def test_performers_fields(client, db):
    """Each performer has the expected fields."""
    await seed_asset_with_prices(db, symbol="AAPL", name="Apple", base_price=150.0, n_days=400)

    resp = await client.get("/api/portfolio/performers?period=1y")
    data = resp.json()
    assert len(data) == 1
    assert set(data[0].keys()) == {"symbol", "name", "type", "change_pct"}

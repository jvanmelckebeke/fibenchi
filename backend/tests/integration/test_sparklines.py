"""Tests for GET /api/sparklines — close-price series by symbol set.

The symbol-addressed sibling of /api/groups/{id}/sparklines. What it buys the
caller is a roster-shaped fetch: one request for symbols spread over several
groups, and no membership requirement at all.
"""

import pytest

from tests.helpers import seed_asset_with_prices

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_returns_requested_symbols(client, db):
    for i, sym in enumerate(["AAPL", "GOOGL", "MSFT"]):
        await seed_asset_with_prices(db, symbol=sym, base_price=100.0 + i * 50, n_days=200)

    resp = await client.get("/api/sparklines?symbols=AAPL&symbols=MSFT&period=3mo")
    assert resp.status_code == 200
    # GOOGL was seeded but not asked for.
    assert set(resp.json()) == {"AAPL", "MSFT"}


async def test_close_only_fields(client, db):
    await seed_asset_with_prices(db, symbol="AAPL", n_days=200)

    resp = await client.get("/api/sparklines?symbols=AAPL&period=3mo")
    points = resp.json()["AAPL"]
    assert len(points) > 0
    assert set(points[0]) == {"date", "close"}


async def test_respects_period(client, db):
    await seed_asset_with_prices(db, symbol="AAPL", n_days=500)

    short = await client.get("/api/sparklines?symbols=AAPL&period=3mo")
    long = await client.get("/api/sparklines?symbols=AAPL&period=1y")
    assert len(long.json()["AAPL"]) > len(short.json()["AAPL"])


async def test_spans_groups_in_one_call(client, db):
    """The point of the endpoint: group membership doesn't shape the fetch.

    One asset sits in the default group, another in no group at all — the board's
    thesis-only case. Both come back from a single request.
    """
    await seed_asset_with_prices(db, symbol="AAPL", n_days=200)
    await seed_asset_with_prices(db, symbol="NVDA", n_days=200, add_to_group=False)

    resp = await client.get("/api/sparklines?symbols=AAPL&symbols=NVDA&period=3mo")
    assert set(resp.json()) == {"AAPL", "NVDA"}


async def test_untracked_symbols_omitted(client, db):
    """No price history means no series — the symbol is dropped, not errored."""
    await seed_asset_with_prices(db, symbol="AAPL", n_days=200)

    resp = await client.get("/api/sparklines?symbols=AAPL&symbols=NOTREAL&period=3mo")
    assert resp.status_code == 200
    assert set(resp.json()) == {"AAPL"}


async def test_no_symbols_returns_empty(client):
    resp = await client.get("/api/sparklines?period=3mo")
    assert resp.status_code == 200
    assert resp.json() == {}


async def test_rejects_unknown_period(client):
    resp = await client.get("/api/sparklines?symbols=AAPL&period=7y")
    assert resp.status_code == 422

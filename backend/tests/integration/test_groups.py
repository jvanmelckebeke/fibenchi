"""Tests for group endpoints — CRUD and batch (sparklines, indicators)."""

import pytest
from datetime import date, timedelta

from app.models import Asset, AssetType, PriceHistory
from app.repositories.group_repo import GroupRepository
from tests.helpers import create_asset_via_api, seed_asset_with_prices

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _get_default_group_id(db):
    group = await GroupRepository(db).get_default()
    return group.id


async def _seed_assets(db, count=3, n_days=200):
    """Create multiple assets in the default group with price history."""
    symbols = ["AAPL", "GOOGL", "MSFT"][:count]
    assets = []
    for i, sym in enumerate(symbols):
        asset = await seed_asset_with_prices(
            db, symbol=sym, base_price=100.0 + i * 50, n_days=n_days,
        )
        assets.append(asset)
    return assets


async def test_create_group(client):
    resp = await client.post("/api/groups", json={"name": "Tech", "description": "Tech stocks"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Tech"
    assert resp.json()["assets"] == []


async def test_list_groups(client):
    await client.post("/api/groups", json={"name": "Tech"})
    await client.post("/api/groups", json={"name": "Energy"})

    resp = await client.get("/api/groups")
    # +1 for the seeded default Watchlist group
    assert len(resp.json()) == 3


async def test_update_group(client):
    resp = await client.post("/api/groups", json={"name": "Tech"})
    gid = resp.json()["id"]

    resp = await client.put(f"/api/groups/{gid}", json={"name": "Technology", "description": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Technology"
    assert resp.json()["description"] == "Updated"


async def test_delete_group(client):
    resp = await client.post("/api/groups", json={"name": "Tech"})
    gid = resp.json()["id"]

    resp = await client.delete(f"/api/groups/{gid}")
    assert resp.status_code == 204


async def test_add_assets_to_group(client):
    a1 = await create_asset_via_api(client, "AAPL", "Apple")
    a2 = await create_asset_via_api(client, "MSFT", "Microsoft")

    resp = await client.post("/api/groups", json={"name": "Tech"})
    gid = resp.json()["id"]

    resp = await client.post(f"/api/groups/{gid}/assets", json={"asset_ids": [a1["id"], a2["id"]]})
    assert resp.status_code == 200
    assert len(resp.json()["assets"]) == 2


async def test_remove_asset_from_group(client):
    a1 = await create_asset_via_api(client, "AAPL", "Apple")
    a2 = await create_asset_via_api(client, "MSFT", "Microsoft")

    resp = await client.post("/api/groups", json={"name": "Tech"})
    gid = resp.json()["id"]

    await client.post(f"/api/groups/{gid}/assets", json={"asset_ids": [a1["id"], a2["id"]]})

    resp = await client.delete(f"/api/groups/{gid}/assets/{a1['id']}")
    assert resp.status_code == 200
    assert len(resp.json()["assets"]) == 1
    assert resp.json()["assets"][0]["symbol"] == "MSFT"


async def test_duplicate_group_name(client):
    await client.post("/api/groups", json={"name": "Tech"})
    resp = await client.post("/api/groups", json={"name": "Tech"})
    assert resp.status_code == 400


# --- GET /groups/:id/sparklines ---

async def test_sparklines_returns_all_symbols(client, db):
    gid = await _get_default_group_id(db)
    await _seed_assets(db, count=3)
    resp = await client.get(f"/api/groups/{gid}/sparklines?period=3mo")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"AAPL", "GOOGL", "MSFT"}


async def test_sparklines_close_only_fields(client, db):
    gid = await _get_default_group_id(db)
    await _seed_assets(db, count=1)
    resp = await client.get(f"/api/groups/{gid}/sparklines?period=3mo")
    data = resp.json()
    points = data["AAPL"]
    assert len(points) > 0
    assert set(points[0].keys()) == {"date", "close"}


async def test_sparklines_respects_period(client, db):
    gid = await _get_default_group_id(db)
    await _seed_assets(db, count=1)
    resp_3mo = await client.get(f"/api/groups/{gid}/sparklines?period=3mo")
    resp_1y = await client.get(f"/api/groups/{gid}/sparklines?period=1y")
    assert len(resp_1y.json()["AAPL"]) > len(resp_3mo.json()["AAPL"])


async def test_sparklines_empty_group(client, db):
    gid = await _get_default_group_id(db)
    resp = await client.get(f"/api/groups/{gid}/sparklines")
    assert resp.status_code == 200
    assert resp.json() == {}


async def test_sparklines_excludes_ungrouped(client, db):
    """Assets not in the group should be excluded from its sparklines."""
    gid = await _get_default_group_id(db)
    assets = await _seed_assets(db, count=2)
    # Remove GOOGL from the default group
    default_group = await GroupRepository(db).get_default()
    default_group.assets = [a for a in default_group.assets if a.id != assets[1].id]
    await db.commit()

    resp = await client.get(f"/api/groups/{gid}/sparklines")
    data = resp.json()
    assert "AAPL" in data
    assert "GOOGL" not in data


# --- GET /groups/:id/indicators ---

async def test_indicators_returns_all_symbols(client, db):
    gid = await _get_default_group_id(db)
    await _seed_assets(db, count=3)
    resp = await client.get(f"/api/groups/{gid}/indicators")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"AAPL", "GOOGL", "MSFT"}


async def test_indicators_has_expected_fields(client, db):
    gid = await _get_default_group_id(db)
    await _seed_assets(db, count=1)
    resp = await client.get(f"/api/groups/{gid}/indicators")
    data = resp.json()
    ind = data["AAPL"]
    # Full snapshot has close, change_pct, and nested values
    assert "values" in ind
    assert "close" in ind
    from app.services.compute.indicators import get_all_output_fields
    expected_fields = set(get_all_output_fields())
    assert expected_fields.issubset(set(ind["values"].keys()))


async def test_indicators_values_not_null_with_enough_data(client, db):
    gid = await _get_default_group_id(db)
    await _seed_assets(db, count=1, n_days=200)
    resp = await client.get(f"/api/groups/{gid}/indicators")
    data = resp.json()
    ind = data["AAPL"]
    values = ind["values"]
    assert values["rsi"] is not None
    assert values["macd"] is not None
    assert values["macd_signal"] is not None
    assert values["macd_hist"] is not None


async def test_indicators_null_with_insufficient_data(client, db):
    """With very few data points, indicators should be null."""
    gid = await _get_default_group_id(db)
    asset = Asset(
        symbol="TINY", name="Tiny Inc.",
        type=AssetType.STOCK, currency="USD",
    )
    db.add(asset)
    await db.flush()
    # Add to default group
    default_group = await GroupRepository(db).get_default()
    default_group.assets.append(asset)
    # Only 5 days of data — not enough for any indicator
    today = date.today()
    for i in range(5):
        d = today - timedelta(days=4 - i)
        db.add(PriceHistory(
            asset_id=asset.id, date=d,
            open=100.0, high=101.0, low=99.0, close=100.0, volume=1000,
        ))
    await db.commit()

    resp = await client.get(f"/api/groups/{gid}/indicators")
    data = resp.json()
    ind = data["TINY"]
    # With insufficient data, values dict should be empty
    assert ind["values"] == {}


async def test_indicators_empty_group(client, db):
    gid = await _get_default_group_id(db)
    resp = await client.get(f"/api/groups/{gid}/indicators")
    assert resp.status_code == 200
    assert resp.json() == {}

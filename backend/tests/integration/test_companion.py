import pytest

from tests.helpers import create_asset_via_api

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_companion_config_shape(client):
    aapl = await create_asset_via_api(client, "AAPL", "Apple Inc.")
    await create_asset_via_api(client, "MSFT", "Microsoft Corp.")

    # A second (non-default) group containing only AAPL — exercises normalization
    # (AAPL is in two groups but defined once in `tickers`).
    tech = (await client.post("/api/groups", json={"name": "Tech", "icon": "cpu"})).json()
    await client.post(f"/api/groups/{tech['id']}/assets", json={"asset_ids": [aapl["id"]]})

    # A tag on AAPL.
    tag = (await client.post("/api/tags", json={"name": "tech", "color": "#3b82f6"})).json()
    await client.post(f"/api/assets/AAPL/tags/{tag['id']}")

    resp = await client.get("/api/companion/config")
    assert resp.status_code == 200
    body = resp.json()

    # Versioned + camelCase serialization for the TS consumer.
    assert body["version"] == 1
    assert "generatedAt" in body

    groups = {g["name"]: g for g in body["groups"]}
    assert groups["Watchlist"]["isDefault"] is True
    assert set(groups["Watchlist"]["symbols"]) == {"AAPL", "MSFT"}
    assert groups["Tech"]["isDefault"] is False
    assert groups["Tech"]["symbols"] == ["AAPL"]

    # Ticker metadata defined once even though AAPL is in two groups.
    assert set(body["tickers"]) == {"AAPL", "MSFT"}
    aapl_ticker = body["tickers"]["AAPL"]
    assert aapl_ticker["name"] == "Apple Inc."
    assert aapl_ticker["type"] == "stock"
    assert aapl_ticker["currency"] == "USD"
    assert aapl_ticker["tags"] == ["tech"]

    assert body["tags"]["tech"] == "#3b82f6"


async def test_companion_config_empty_is_valid(client):
    # Only the seeded default Watchlist exists; bundle should still be well-formed.
    body = (await client.get("/api/companion/config")).json()
    assert body["version"] == 1
    assert isinstance(body["groups"], list)
    assert isinstance(body["tickers"], dict)
    assert isinstance(body["tags"], dict)

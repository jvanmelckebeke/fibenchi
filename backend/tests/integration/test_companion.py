import json
import pathlib
from unittest.mock import AsyncMock, patch

import pytest

from tests.helpers import create_asset_via_api, seed_asset_with_prices

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
    # Symbols are sorted deterministically (group_assets has no ordinal column).
    assert groups["Watchlist"]["symbols"] == ["AAPL", "MSFT"]
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


async def test_companion_config_theses(client):
    await create_asset_via_api(client, "AAPL", "Apple Inc.")
    await create_asset_via_api(client, "MSFT", "Microsoft Corp.")
    # In a thesis but in no group: the app can only name it through tickers.
    solo = await create_asset_via_api(client, "XOM", "Exxon Mobil", attach_to_watchlist=False)
    ids = {a["symbol"]: a["id"] for a in (await client.get("/api/assets")).json()}

    zeta = (await client.post("/api/theses", json={"name": "Zeta", "color": "#ef4444"})).json()
    alpha = (await client.post("/api/theses", json={"name": "Alpha"})).json()
    await client.post(f"/api/theses/{zeta['id']}/assets", json={"asset_ids": [solo["id"], ids["AAPL"]]})
    await client.post(f"/api/theses/{alpha['id']}/assets", json={"asset_ids": [ids["MSFT"]]})

    body = (await client.get("/api/companion/config")).json()

    expected_order = [t["name"] for t in (await client.get("/api/theses")).json()]
    assert [t["name"] for t in body["theses"]] == expected_order == ["Alpha", "Zeta"]
    assert body["theses"][0] == {"name": "Alpha", "color": "#3b82f6", "symbols": ["MSFT"]}
    assert body["theses"][1] == {"name": "Zeta", "color": "#ef4444", "symbols": ["AAPL", "XOM"]}

    assert body["tickers"]["XOM"]["name"] == "Exxon Mobil"
    assert all("XOM" not in g["symbols"] for g in body["groups"])


async def test_companion_config_no_theses_is_empty_list(client):
    body = (await client.get("/api/companion/config")).json()
    assert body["theses"] == []


async def test_companion_portfolio_index_shape(client, db):
    await seed_asset_with_prices(db, symbol="AAPL", name="Apple", base_price=150.0, n_days=400)

    resp = await client.get("/api/companion/portfolio-index?period=1y")
    assert resp.status_code == 200
    body = resp.json()
    web = (await client.get("/api/portfolio/index?period=1y")).json()

    assert body["version"] == 1
    assert "generatedAt" in body
    assert body["period"] == "1y"
    assert body["dates"] == web["dates"]
    assert body["values"] == web["values"]
    assert body["current"] == web["current"]
    assert body["change"] == web["change"]
    assert body["changePct"] == web["change_pct"]
    assert len(body["dates"]) > 0


async def test_companion_portfolio_index_reuses_service(client):
    index = {"dates": ["2026-01-02"], "values": [1000.0], "current": 1000.0, "change": 0.0, "change_pct": 0.0}
    with patch(
        "app.services.companion_service.compute_portfolio_index", AsyncMock(return_value=index)
    ) as compute:
        body = (await client.get("/api/companion/portfolio-index?period=3mo")).json()
    assert compute.await_args.args[1] == "3mo"
    assert body["period"] == "3mo"
    assert body["dates"] == ["2026-01-02"]
    assert body["current"] == 1000.0
    assert body["change"] == 0.0


async def test_companion_portfolio_index_empty_is_null(client):
    body = (await client.get("/api/companion/portfolio-index")).json()
    assert body["period"] == "1y"
    assert body["dates"] == []
    assert body["values"] == []
    assert body["current"] is None
    assert body["change"] is None
    assert body["changePct"] is None


async def test_companion_portfolio_index_rejects_unknown_period(client):
    resp = await client.get("/api/companion/portfolio-index?period=10y")
    assert resp.status_code == 422


async def test_companion_schema_artifacts_are_fresh():
    """The committed JSON Schemas are the codegen input for the companion app, so
    they must stay in lock-step with the Pydantic SoT. If this fails, regenerate:

        python -m scripts.export_companion_schema
    """
    from scripts.export_companion_schema import ARTIFACTS

    backend = pathlib.Path(__file__).parents[2]
    for filename, model in ARTIFACTS.items():
        on_disk = json.loads((backend / filename).read_text())
        assert model.model_json_schema(by_alias=True) == on_disk, (
            f"{filename} is stale — run: python -m scripts.export_companion_schema"
        )

import pytest
from unittest.mock import patch


pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_list_assets_empty(client):
    resp = await client.get("/api/assets")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_asset_with_name(client):
    resp = await client.post("/api/assets", json={
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "type": "stock",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["symbol"] == "AAPL"
    assert data["name"] == "Apple Inc."
    assert data["type"] == "stock"
    assert data["currency"] == "USD"


async def test_create_asset_auto_resolve(client):
    mock_info = {"symbol": "NVDA", "name": "NVIDIA Corporation", "type": "EQUITY"}
    with patch("app.services.asset_service.validate_symbol", return_value=mock_info):
        resp = await client.post("/api/assets", json={"symbol": "nvda"})
    assert resp.status_code == 201
    assert resp.json()["symbol"] == "NVDA"
    assert resp.json()["name"] == "NVIDIA Corporation"
    assert resp.json()["currency"] == "USD"


async def test_create_asset_with_currency(client):
    mock_info = {"symbol": "VWCE.DE", "name": "Vanguard FTSE All-World", "type": "ETF", "currency": "EUR"}
    with patch("app.services.asset_service.validate_symbol", return_value=mock_info):
        resp = await client.post("/api/assets", json={"symbol": "vwce.de"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["symbol"] == "VWCE.DE"
    assert data["currency"] == "EUR"
    assert data["type"] == "etf"


async def test_create_asset_invalid_symbol(client):
    with patch("app.services.asset_service.validate_symbol", return_value=None):
        resp = await client.post("/api/assets", json={"symbol": "XXXX"})
    assert resp.status_code == 404


async def test_create_duplicate_asset(client):
    await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple"})
    resp = await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple"})
    assert resp.status_code == 400


async def test_delete_asset(client):
    await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple"})
    resp = await client.delete("/api/assets/AAPL")
    assert resp.status_code == 204

    resp = await client.get("/api/assets")
    assert resp.json() == []


async def test_delete_nonexistent_asset(client):
    resp = await client.delete("/api/assets/NOPE")
    assert resp.status_code == 404


async def test_list_assets_returns_created(client):
    await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple"})
    await client.post("/api/assets", json={"symbol": "MSFT", "name": "Microsoft"})

    resp = await client.get("/api/assets")
    assert resp.status_code == 200
    symbols = [a["symbol"] for a in resp.json()]
    assert symbols == ["AAPL", "MSFT"]

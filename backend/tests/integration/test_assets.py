from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest

from app.services import asset_service


pytestmark = pytest.mark.asyncio(loop_scope="function")


@contextmanager
def _mock_validate(*, return_value=None, side_effect=None):
    """Override the autouse ``yahoo_client`` mock's ``validate`` for the test.

    The conftest ``mock_yahoo_validate`` fixture rebinds
    ``asset_service.yahoo_client`` to a fresh MagicMock per test; this
    helper just configures its ``validate`` attribute for the duration of
    the with-block so each test can specify its own response.
    """
    original = asset_service.yahoo_client.validate
    if side_effect is not None:
        asset_service.yahoo_client.validate = AsyncMock(side_effect=side_effect)
    else:
        asset_service.yahoo_client.validate = AsyncMock(return_value=return_value)
    try:
        yield
    finally:
        asset_service.yahoo_client.validate = original


async def test_list_assets_empty(client):
    resp = await client.get("/api/assets")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_asset_with_name(client):
    mock_info = {"symbol": "AAPL", "name": "Apple Inc.", "type": "EQUITY", "currency": "USD", "currency_code": "USD"}
    with _mock_validate(return_value=mock_info):
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
    mock_info = {"symbol": "NVDA", "name": "NVIDIA Corporation", "type": "EQUITY", "currency": "USD", "currency_code": "USD"}
    with _mock_validate(return_value=mock_info):
        resp = await client.post("/api/assets", json={"symbol": "nvda"})
    assert resp.status_code == 201
    assert resp.json()["symbol"] == "NVDA"
    assert resp.json()["name"] == "NVIDIA Corporation"
    assert resp.json()["currency"] == "USD"


async def test_create_asset_with_currency(client):
    mock_info = {"symbol": "VWCE.DE", "name": "Vanguard FTSE All-World", "type": "ETF", "currency": "EUR", "currency_code": "EUR"}
    with _mock_validate(return_value=mock_info):
        resp = await client.post("/api/assets", json={"symbol": "vwce.de"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["symbol"] == "VWCE.DE"
    assert data["currency"] == "EUR"
    assert data["type"] == "etf"


async def test_create_asset_krw_currency(client):
    """Regression test for #213: KOSPI assets should have KRW currency."""
    mock_info = {"symbol": "006260.KS", "name": "LS Corp", "type": "EQUITY", "currency": "KRW", "currency_code": "KRW"}
    with _mock_validate(return_value=mock_info):
        resp = await client.post("/api/assets", json={"symbol": "006260.KS"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["symbol"] == "006260.KS"
    assert data["currency"] == "KRW"
    assert data["name"] == "LS Corp"


async def test_create_asset_invalid_symbol(client):
    with _mock_validate(return_value=None):
        resp = await client.post("/api/assets", json={"symbol": "XXXX"})
    assert resp.status_code == 404


async def test_create_duplicate_asset_returns_existing(client):
    """Creating an asset that already exists returns the existing record (idempotent)."""
    mock_info = {"symbol": "AAPL", "name": "Apple", "type": "EQUITY", "currency": "USD", "currency_code": "USD"}
    with _mock_validate(return_value=mock_info):
        resp1 = await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple"})
        resp2 = await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple"})
    assert resp2.status_code == 201
    assert resp2.json()["id"] == resp1.json()["id"]


async def test_delete_asset(client):
    """``DELETE /api/assets/{symbol}`` is a soft-delete: the row is preserved
    so pseudo-ETF constituent relationships stay intact. The asset remains
    visible in the listing — only group membership is removed."""
    mock_info = {"symbol": "AAPL", "name": "Apple", "type": "EQUITY", "currency": "USD", "currency_code": "USD"}
    with _mock_validate(return_value=mock_info):
        await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple"})
    resp = await client.delete("/api/assets/AAPL")
    assert resp.status_code == 204

    resp = await client.get("/api/assets")
    assert [a["symbol"] for a in resp.json()] == ["AAPL"]


async def test_delete_nonexistent_asset(client):
    resp = await client.delete("/api/assets/NOPE")
    assert resp.status_code == 404


async def test_list_assets_returns_created(client):
    """``GET /api/assets`` returns every asset, ordered by symbol —
    including orphans not yet attached to any group."""
    mock_aapl = {"symbol": "AAPL", "name": "Apple", "type": "EQUITY", "currency": "USD", "currency_code": "USD"}
    mock_msft = {"symbol": "MSFT", "name": "Microsoft", "type": "EQUITY", "currency": "USD", "currency_code": "USD"}
    with _mock_validate(side_effect=[mock_aapl, mock_msft]):
        await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple"})
        await client.post("/api/assets", json={"symbol": "MSFT", "name": "Microsoft"})

    resp = await client.get("/api/assets")
    assert resp.status_code == 200
    symbols = [a["symbol"] for a in resp.json()]
    assert symbols == ["AAPL", "MSFT"]


async def test_list_assets_includes_orphans(client):
    """Regression for #507: a freshly POSTed asset must appear in GET /api/assets
    even before it has been attached to any group."""
    mock_info = {"symbol": "OKLO", "name": "Oklo", "type": "EQUITY", "currency": "USD", "currency_code": "USD"}
    with _mock_validate(return_value=mock_info):
        await client.post("/api/assets", json={"symbol": "OKLO", "name": "Oklo"})

    resp = await client.get("/api/assets")
    assert resp.status_code == 200
    symbols = [a["symbol"] for a in resp.json()]
    assert "OKLO" in symbols

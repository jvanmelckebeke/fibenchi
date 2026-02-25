"""Integration tests for the search router."""

from unittest.mock import AsyncMock, patch

import pytest

from app.models.symbol_directory import SymbolDirectory
from tests.conftest import TestSession

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _seed_symbols(db):
    """Seed some symbols into the symbol_directory for local search."""
    symbols = [
        SymbolDirectory(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ", type="stock"),
        SymbolDirectory(symbol="AMZN", name="Amazon.com Inc.", exchange="NASDAQ", type="stock"),
        SymbolDirectory(symbol="AMD", name="Advanced Micro Devices", exchange="NASDAQ", type="stock"),
        SymbolDirectory(symbol="ABBV", name="AbbVie Inc.", exchange="NYSE", type="stock"),
        SymbolDirectory(symbol="ABT", name="Abbott Laboratories", exchange="NYSE", type="stock"),
        SymbolDirectory(symbol="ABNB", name="Airbnb Inc.", exchange="NASDAQ", type="stock"),
        SymbolDirectory(symbol="ADBE", name="Adobe Inc.", exchange="NASDAQ", type="stock"),
        SymbolDirectory(symbol="AVGO", name="Broadcom Inc.", exchange="NASDAQ", type="stock"),
    ]
    db.add_all(symbols)
    await db.commit()


class TestSearchSymbols:
    async def test_search_requires_query(self, client):
        resp = await client.get("/api/search")
        assert resp.status_code == 422

    async def test_empty_query_rejected(self, client):
        resp = await client.get("/api/search", params={"q": ""})
        assert resp.status_code == 422

    async def test_local_source(self, client, db):
        await _seed_symbols(db)
        resp = await client.get("/api/search", params={"q": "aapl", "source": "local"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["symbol"] == "AAPL"

    async def test_local_search_partial_match(self, client, db):
        await _seed_symbols(db)
        resp = await client.get("/api/search", params={"q": "apple", "source": "local"})
        assert resp.status_code == 200
        data = resp.json()
        assert any(d["symbol"] == "AAPL" for d in data)

    @patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
    async def test_yahoo_source(self, mock_yahoo, client, db):
        mock_yahoo.return_value = {"quotes": [
            {"symbol": "TSLA", "shortname": "Tesla Inc.", "exchDisp": "NASDAQ", "quoteType": "EQUITY"},
        ]}
        resp = await client.get("/api/search", params={"q": "tesla", "source": "yahoo"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["symbol"] == "TSLA"
        assert data[0]["type"] == "stock"

    @patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
    async def test_all_source_uses_local_first(self, mock_yahoo, client, db):
        await _seed_symbols(db)
        # With 8 local results for "a", should not call Yahoo
        resp = await client.get("/api/search", params={"q": "a", "source": "all"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
    async def test_all_source_falls_back_to_yahoo(self, mock_yahoo, client, db):
        """With fewer than 8 local results, should query Yahoo."""
        mock_yahoo.return_value = {"quotes": [
            {"symbol": "XYZQ", "shortname": "XYZ Corp", "exchDisp": "NYSE", "quoteType": "EQUITY"},
        ]}
        resp = await client.get("/api/search", params={"q": "xyzq", "source": "all"})
        assert resp.status_code == 200
        data = resp.json()
        assert any(d["symbol"] == "XYZQ" for d in data)

    @patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
    async def test_yahoo_filters_non_equity_etf(self, mock_yahoo, client):
        mock_yahoo.return_value = {"quotes": [
            {"symbol": "BTCUSD", "shortname": "Bitcoin", "exchDisp": "CCC", "quoteType": "CRYPTOCURRENCY"},
            {"symbol": "AAPL", "shortname": "Apple", "exchDisp": "NASDAQ", "quoteType": "EQUITY"},
        ]}
        resp = await client.get("/api/search", params={"q": "btc", "source": "yahoo"})
        assert resp.status_code == 200
        data = resp.json()
        # CRYPTOCURRENCY should be filtered out
        symbols = [d["symbol"] for d in data]
        assert "BTCUSD" not in symbols

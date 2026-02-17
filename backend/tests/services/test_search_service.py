"""Unit tests for search_service — DB-backed symbol directory with Yahoo fallback."""

import pytest
from unittest.mock import AsyncMock, patch

from app.models.symbol_directory import SymbolDirectory
from app.services.search_service import search_symbols, _parse_yahoo_results

pytestmark = pytest.mark.asyncio(loop_scope="function")


def _yahoo_response(*items):
    """Build a Yahoo-style search response with given quote items."""
    return {"quotes": list(items)}


def _equity(symbol: str, name: str = ""):
    return {"symbol": symbol, "shortname": name, "quoteType": "EQUITY", "exchDisp": "NYSE"}


def _etf(symbol: str, name: str = ""):
    return {"symbol": symbol, "shortname": name, "quoteType": "ETF", "exchDisp": "NYSE Arca"}


def _mutual_fund(symbol: str, name: str = ""):
    return {"symbol": symbol, "shortname": name, "quoteType": "MUTUALFUND", "exchDisp": "NAS"}


def test_parse_yahoo_results_filters_non_equity_etf():
    quotes = [
        _equity("AAPL", "Apple Inc."),
        _mutual_fund("VFINX", "Vanguard 500"),
        _etf("SPY", "SPDR S&P 500"),
    ]
    result = _parse_yahoo_results(quotes)
    assert len(result) == 2
    symbols = [r["symbol"] for r in result]
    assert "AAPL" in symbols
    assert "SPY" in symbols
    assert "VFINX" not in symbols


def test_parse_yahoo_results_caps_at_8():
    quotes = [_equity(f"SYM{i}", f"Company {i}") for i in range(12)]
    result = _parse_yahoo_results(quotes)
    assert len(result) == 8


def test_parse_yahoo_results_empty():
    result = _parse_yahoo_results([])
    assert result == []


@patch("app.services.search_service._upsert_symbols", new_callable=AsyncMock)
@patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
async def test_search_queries_yahoo_when_db_empty(mock_yahoo, mock_upsert, db):
    mock_yahoo.return_value = _yahoo_response(
        _equity("AAPL", "Apple Inc."),
        _etf("SPY", "SPDR S&P 500"),
    )

    result = await search_symbols("apple", db)

    assert len(result) == 2
    mock_yahoo.assert_awaited_once_with("apple", first_quote=False)
    mock_upsert.assert_awaited_once()


@patch("app.services.search_service._upsert_symbols", new_callable=AsyncMock)
@patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
async def test_search_strips_and_lowercases_query(mock_yahoo, mock_upsert, db):
    mock_yahoo.return_value = _yahoo_response(_equity("AAPL", "Apple"))

    await search_symbols("  AAPL  ", db)

    mock_yahoo.assert_awaited_once_with("aapl", first_quote=False)


@patch("app.services.search_service._upsert_symbols", new_callable=AsyncMock)
@patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
async def test_search_returns_local_when_enough_results(mock_yahoo, mock_upsert, db):
    # Seed 8+ symbols into the DB
    for i in range(10):
        db.add(SymbolDirectory(symbol=f"AAPL{i}", name=f"Apple {i}", exchange="NYSE", type="stock"))
    await db.commit()

    result = await search_symbols("aapl", db)

    assert len(result) >= 8
    mock_yahoo.assert_not_awaited()  # Should not call Yahoo when local has enough


@patch("app.services.search_service._upsert_symbols", new_callable=AsyncMock)
@patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
async def test_search_falls_back_to_yahoo_when_few_local(mock_yahoo, mock_upsert, db):
    # Seed only 2 symbols
    db.add(SymbolDirectory(symbol="AAPL", name="Apple Inc.", exchange="NYSE", type="stock"))
    db.add(SymbolDirectory(symbol="AAPLX", name="Apple Extra", exchange="NYSE", type="stock"))
    await db.commit()

    mock_yahoo.return_value = _yahoo_response(
        _equity("AAPL", "Apple Inc."),
        _equity("AAPL2", "Apple 2"),
    )

    result = await search_symbols("aapl", db)

    mock_yahoo.assert_awaited_once()
    assert len(result) == 2  # Yahoo results take priority


@patch("app.services.search_service._upsert_symbols", new_callable=AsyncMock)
@patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
async def test_search_returns_empty_when_no_matches(mock_yahoo, mock_upsert, db):
    mock_yahoo.return_value = _yahoo_response(
        _mutual_fund("VFINX", "Vanguard 500"),
    )

    result = await search_symbols("vanguard", db)

    assert result == []

"""Unit tests for search_service — symbol search with TTL cache."""

import pytest
from unittest.mock import AsyncMock, patch

import app.services.search_service as search_mod
from app.services.search_service import search_symbols

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


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the module-level search cache before each test."""
    search_mod._cache.clear()
    yield
    search_mod._cache.clear()


@patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
async def test_search_returns_filtered_results(mock_yahoo):
    mock_yahoo.return_value = _yahoo_response(
        _equity("AAPL", "Apple Inc."),
        _mutual_fund("VFINX", "Vanguard 500"),
        _etf("SPY", "SPDR S&P 500"),
    )

    result = await search_symbols("apple")

    assert len(result) == 2
    symbols = [r["symbol"] for r in result]
    assert "AAPL" in symbols
    assert "SPY" in symbols
    assert "VFINX" not in symbols


@patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
async def test_search_strips_and_lowercases_query(mock_yahoo):
    mock_yahoo.return_value = _yahoo_response(_equity("AAPL", "Apple"))

    await search_symbols("  AAPL  ")

    mock_yahoo.assert_awaited_once_with("aapl", first_quote=False)


@patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
async def test_search_caps_results_at_8(mock_yahoo):
    quotes = [_equity(f"SYM{i}", f"Company {i}") for i in range(12)]
    mock_yahoo.return_value = _yahoo_response(*quotes)

    result = await search_symbols("sym")

    assert len(result) == 8


@patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
async def test_search_returns_cached_result_on_second_call(mock_yahoo):
    mock_yahoo.return_value = _yahoo_response(_equity("AAPL", "Apple"))

    first = await search_symbols("apple")
    second = await search_symbols("apple")

    mock_yahoo.assert_awaited_once()  # Only one call — second hit cache
    assert first == second


@patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
async def test_search_returns_empty_list_when_no_matches(mock_yahoo):
    mock_yahoo.return_value = _yahoo_response(
        _mutual_fund("VFINX", "Vanguard 500"),
    )

    result = await search_symbols("vanguard")

    assert result == []


@patch("app.services.search_service.yahoo_search", new_callable=AsyncMock)
async def test_cache_eviction_when_max_reached(mock_yahoo):
    original_max = search_mod._CACHE_MAX
    search_mod._CACHE_MAX = 3
    try:
        for i in range(4):
            mock_yahoo.return_value = _yahoo_response(_equity(f"S{i}", f"Co {i}"))
            await search_symbols(f"query{i}")

        # Cache should have evicted the oldest entry
        assert len(search_mod._cache) == 3
        assert "query0" not in search_mod._cache
        assert "query3" in search_mod._cache
    finally:
        search_mod._CACHE_MAX = original_max

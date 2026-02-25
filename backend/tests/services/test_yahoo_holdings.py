"""Tests for Yahoo Finance ETF holdings fetching."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.yahoo.holdings import (
    _fetch_etf_holdings_uncached,
    _holdings_cache,
    fetch_etf_holdings,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


_MOCK_FUND_INFO = {
    "holdings": [
        {"symbol": "AAPL", "holdingName": "Apple Inc.", "holdingPercent": 0.072},
        {"symbol": "MSFT", "holdingName": "Microsoft Corp.", "holdingPercent": 0.065},
        {"symbol": "AMZN", "holdingName": "Amazon.com Inc.", "holdingPercent": 0.035},
    ],
    "sectorWeightings": [
        {"technology": 0.29},
        {"healthcare": 0.14},
        {"financial_services": 0.13},
        {"consumer_cyclical": 0.10},
        {"industrials": 0.09},
    ],
}


class TestFetchEtfHoldingsUncached:
    @patch("app.services.yahoo.holdings.Ticker")
    def test_returns_holdings_and_sectors(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.fund_holding_info = {"SPY": _MOCK_FUND_INFO}
        mock_ticker_cls.return_value = ticker

        result = _fetch_etf_holdings_uncached("SPY")

        assert result is not None
        assert len(result["top_holdings"]) == 3
        assert result["top_holdings"][0]["symbol"] == "AAPL"
        assert result["top_holdings"][0]["percent"] == 7.2
        assert result["top_holdings"][1]["name"] == "Microsoft Corp."

    @patch("app.services.yahoo.holdings.Ticker")
    def test_sector_names_are_mapped(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.fund_holding_info = {"SPY": _MOCK_FUND_INFO}
        mock_ticker_cls.return_value = ticker

        result = _fetch_etf_holdings_uncached("SPY")
        sector_names = [s["sector"] for s in result["sector_weightings"]]

        assert "Technology" in sector_names
        assert "Healthcare" in sector_names
        assert "Financial Services" in sector_names

    @patch("app.services.yahoo.holdings.Ticker")
    def test_sectors_sorted_descending(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.fund_holding_info = {"SPY": _MOCK_FUND_INFO}
        mock_ticker_cls.return_value = ticker

        result = _fetch_etf_holdings_uncached("SPY")
        pcts = [s["percent"] for s in result["sector_weightings"]]
        assert pcts == sorted(pcts, reverse=True)

    @patch("app.services.yahoo.holdings.Ticker")
    def test_zero_weight_sectors_excluded(self, mock_ticker_cls):
        info = {"holdings": [], "sectorWeightings": [{"energy": 0.0}, {"technology": 0.15}]}
        ticker = MagicMock()
        ticker.fund_holding_info = {"SPY": info}
        mock_ticker_cls.return_value = ticker

        result = _fetch_etf_holdings_uncached("SPY")
        assert len(result["sector_weightings"]) == 1
        assert result["sector_weightings"][0]["sector"] == "Technology"

    @patch("app.services.yahoo.holdings.Ticker")
    def test_total_percent_calculated(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.fund_holding_info = {"SPY": _MOCK_FUND_INFO}
        mock_ticker_cls.return_value = ticker

        result = _fetch_etf_holdings_uncached("SPY")
        expected = round(7.2 + 6.5 + 3.5, 2)
        assert result["total_percent"] == expected

    @patch("app.services.yahoo.holdings.Ticker")
    def test_returns_none_for_non_etf(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.fund_holding_info = {"AAPL": None}
        mock_ticker_cls.return_value = ticker

        result = _fetch_etf_holdings_uncached("AAPL")
        assert result is None

    @patch("app.services.yahoo.holdings.Ticker")
    def test_returns_none_for_string_error(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.fund_holding_info = {"AAPL": "No fundamentals data found"}
        mock_ticker_cls.return_value = ticker

        result = _fetch_etf_holdings_uncached("AAPL")
        assert result is None

    @patch("app.services.yahoo.holdings.Ticker")
    def test_handles_unknown_sector_key(self, mock_ticker_cls):
        info = {"holdings": [], "sectorWeightings": [{"unknown_sector": 0.05}]}
        ticker = MagicMock()
        ticker.fund_holding_info = {"XYZ": info}
        mock_ticker_cls.return_value = ticker

        result = _fetch_etf_holdings_uncached("XYZ")
        assert result["sector_weightings"][0]["sector"] == "unknown_sector"

    @patch("app.services.yahoo.holdings.Ticker")
    def test_handles_empty_holdings_list(self, mock_ticker_cls):
        info = {"holdings": [], "sectorWeightings": []}
        ticker = MagicMock()
        ticker.fund_holding_info = {"SPY": info}
        mock_ticker_cls.return_value = ticker

        result = _fetch_etf_holdings_uncached("SPY")
        assert result["top_holdings"] == []
        assert result["total_percent"] == 0.0


class TestFetchEtfHoldingsCaching:
    @patch("app.services.yahoo.holdings.Ticker")
    async def test_caches_result(self, mock_ticker_cls):
        _holdings_cache._data.clear()

        ticker = MagicMock()
        ticker.fund_holding_info = {"SPY": _MOCK_FUND_INFO}
        mock_ticker_cls.return_value = ticker

        result1 = await fetch_etf_holdings("SPY")
        result2 = await fetch_etf_holdings("SPY")

        # Only one Ticker instantiation due to cache hit
        assert mock_ticker_cls.call_count == 1
        assert result1 == result2

        _holdings_cache._data.clear()

    @patch("app.services.yahoo.holdings.Ticker")
    async def test_uppercase_cache_key(self, mock_ticker_cls):
        _holdings_cache._data.clear()

        ticker = MagicMock()
        ticker.fund_holding_info = {"spy": _MOCK_FUND_INFO}
        mock_ticker_cls.return_value = ticker

        await fetch_etf_holdings("spy")
        # Cache key should be uppercase
        assert _holdings_cache.get_value("SPY") is not None

        _holdings_cache._data.clear()

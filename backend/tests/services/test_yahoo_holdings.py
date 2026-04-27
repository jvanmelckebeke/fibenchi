"""Tests for Yahoo Finance ETF holdings fetching."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.yahoo import yahoo_client
from app.services.yahoo.client import _parse_holdings

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


class TestParseHoldings:
    """``_parse_holdings`` is a pure function — no Yahoo I/O involved."""

    def test_returns_holdings_and_sectors(self):
        result = _parse_holdings(_MOCK_FUND_INFO)

        assert result is not None
        assert len(result["top_holdings"]) == 3
        assert result["top_holdings"][0]["symbol"] == "AAPL"
        assert result["top_holdings"][0]["percent"] == 7.2
        assert result["top_holdings"][1]["name"] == "Microsoft Corp."

    def test_sector_names_are_mapped(self):
        result = _parse_holdings(_MOCK_FUND_INFO)
        sector_names = [s["sector"] for s in result["sector_weightings"]]
        assert "Technology" in sector_names
        assert "Healthcare" in sector_names
        assert "Financial Services" in sector_names

    def test_sectors_sorted_descending(self):
        result = _parse_holdings(_MOCK_FUND_INFO)
        pcts = [s["percent"] for s in result["sector_weightings"]]
        assert pcts == sorted(pcts, reverse=True)

    def test_zero_weight_sectors_excluded(self):
        info = {"holdings": [], "sectorWeightings": [{"energy": 0.0}, {"technology": 0.15}]}
        result = _parse_holdings(info)
        assert len(result["sector_weightings"]) == 1
        assert result["sector_weightings"][0]["sector"] == "Technology"

    def test_total_percent_calculated(self):
        result = _parse_holdings(_MOCK_FUND_INFO)
        expected = round(7.2 + 6.5 + 3.5, 2)
        assert result["total_percent"] == expected

    def test_returns_none_for_empty_info(self):
        assert _parse_holdings({}) is None

    def test_handles_unknown_sector_key(self):
        info = {"holdings": [], "sectorWeightings": [{"unknown_sector": 0.05}]}
        result = _parse_holdings(info)
        assert result["sector_weightings"][0]["sector"] == "unknown_sector"

    def test_handles_empty_holdings_list(self):
        info = {"holdings": [], "sectorWeightings": []}
        result = _parse_holdings(info)
        assert result["top_holdings"] == []
        assert result["total_percent"] == 0.0


class TestHoldings:
    @patch("app.services.yahoo.client.Ticker")
    async def test_returns_none_for_non_etf(self, mock_ticker_cls):
        yahoo_client._holdings_cache.clear()
        ticker = MagicMock()
        ticker.fund_holding_info = {"AAPL": None}
        mock_ticker_cls.return_value = ticker

        result = await yahoo_client.holdings("AAPL")
        assert result is None

    @patch("app.services.yahoo.client.Ticker")
    async def test_returns_none_for_string_error(self, mock_ticker_cls):
        yahoo_client._holdings_cache.clear()
        ticker = MagicMock()
        ticker.fund_holding_info = {"AAPL": "No fundamentals data found"}
        mock_ticker_cls.return_value = ticker

        result = await yahoo_client.holdings("AAPL")
        assert result is None

    @patch("app.services.yahoo.client.Ticker")
    async def test_caches_result(self, mock_ticker_cls):
        yahoo_client._holdings_cache.clear()

        ticker = MagicMock()
        ticker.fund_holding_info = {"SPY": _MOCK_FUND_INFO}
        mock_ticker_cls.return_value = ticker

        result1 = await yahoo_client.holdings("SPY")
        result2 = await yahoo_client.holdings("SPY")

        # Only one Ticker instantiation due to cache hit.
        assert mock_ticker_cls.call_count == 1
        assert result1 == result2

        yahoo_client._holdings_cache.clear()

    @patch("app.services.yahoo.client.Ticker")
    async def test_uppercase_cache_key(self, mock_ticker_cls):
        yahoo_client._holdings_cache.clear()

        ticker = MagicMock()
        ticker.fund_holding_info = {"spy": _MOCK_FUND_INFO}
        mock_ticker_cls.return_value = ticker

        await yahoo_client.holdings("spy")
        # Cache key is normalised to uppercase
        assert yahoo_client._holdings_cache.get_value("SPY") is not None

        yahoo_client._holdings_cache.clear()

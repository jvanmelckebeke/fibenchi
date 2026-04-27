"""Tests for Yahoo Finance real-time quote fetching."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.yahoo import yahoo_client
from app.services.yahoo.client import _parse_quotes, _sanitize_float
from app.services.yahoo.rate_limit import crumb_rejected


class TestSanitize:
    def test_none_returns_none(self):
        assert _sanitize_float(None) is None

    def test_nan_returns_none(self):
        assert _sanitize_float(float("nan")) is None

    def test_inf_returns_none(self):
        assert _sanitize_float(float("inf")) is None

    def test_neg_inf_returns_none(self):
        assert _sanitize_float(float("-inf")) is None

    def test_valid_float_passthrough(self):
        assert _sanitize_float(42.5) == 42.5

    def test_zero_passthrough(self):
        assert _sanitize_float(0.0) == 0.0


class TestParseQuotes:
    def test_basic_quote(self):
        price_data = {
            "AAPL": {
                "currency": "USD",
                "regularMarketPrice": 185.50,
                "regularMarketPreviousClose": 184.00,
                "regularMarketChange": 1.50,
                "regularMarketChangePercent": 0.0082,
                "regularMarketVolume": 50_000_000,
                "averageDailyVolume10Day": 55_000_000,
                "marketState": "REGULAR",
            }
        }

        results = _parse_quotes(["AAPL"], price_data)

        assert len(results) == 1
        q = results[0]
        assert q["symbol"] == "AAPL"
        assert q["price"] == 185.50
        assert q["previous_close"] == 184.0
        assert q["change"] == 1.50
        assert q["change_percent"] == 0.82
        assert q["volume"] == 50_000_000
        assert q["avg_volume"] == 55_000_000
        assert q["currency"] == "USD"
        assert q["market_state"] == "REGULAR"

    def test_non_dict_info_returns_symbol_only(self):
        price_data = {"AAPL": "No data found"}
        results = _parse_quotes(["AAPL"], price_data)
        assert len(results) == 1
        assert results[0] == {"symbol": "AAPL"}

    def test_nan_values_sanitized(self):
        price_data = {
            "AAPL": {
                "currency": "USD",
                "regularMarketPrice": float("nan"),
                "regularMarketPreviousClose": None,
                "regularMarketChange": float("inf"),
                "regularMarketChangePercent": float("nan"),
                "regularMarketVolume": None,
                "averageDailyVolume10Day": None,
                "marketState": "REGULAR",
            }
        }
        results = _parse_quotes(["AAPL"], price_data)
        q = results[0]
        assert q["price"] is None
        assert q["change"] is None
        assert q["change_percent"] is None

    def test_missing_symbol_in_price_data(self):
        results = _parse_quotes(["AAPL"], {})

        assert len(results) == 1
        q = results[0]
        assert q["symbol"] == "AAPL"
        assert q["price"] is None
        assert q["currency"] == "USD"

    def test_currency_normalization_gbp(self):
        price_data = {
            "HSBA.L": {
                "currency": "GBp",
                "regularMarketPrice": 6500.0,
                "regularMarketPreviousClose": 6400.0,
                "regularMarketChange": 100.0,
                "regularMarketChangePercent": 0.015625,
                "regularMarketVolume": 10_000_000,
                "averageDailyVolume10Day": None,
                "marketState": "REGULAR",
            }
        }
        results = _parse_quotes(["HSBA.L"], price_data)
        q = results[0]
        assert q["currency"] == "GBP"
        assert q["price"] == 65.0
        assert q["previous_close"] == 64.0
        assert q["change"] == 1.0

    def test_multiple_symbols(self):
        price_data = {
            "AAPL": {
                "currency": "USD", "regularMarketPrice": 185.0,
                "regularMarketPreviousClose": 184.0, "regularMarketChange": 1.0,
                "regularMarketChangePercent": 0.005, "regularMarketVolume": 50_000_000,
                "averageDailyVolume10Day": None, "marketState": "REGULAR",
            },
            "MSFT": {
                "currency": "USD", "regularMarketPrice": 420.0,
                "regularMarketPreviousClose": 418.0, "regularMarketChange": 2.0,
                "regularMarketChangePercent": 0.005, "regularMarketVolume": 30_000_000,
                "averageDailyVolume10Day": None, "marketState": "REGULAR",
            },
        }
        results = _parse_quotes(["AAPL", "MSFT"], price_data)
        assert len(results) == 2
        assert results[0]["symbol"] == "AAPL"
        assert results[1]["symbol"] == "MSFT"


class TestCrumbRejected:
    def test_all_invalid(self):
        assert crumb_rejected({"AAPL": "Invalid Crumb", "MSFT": "Invalid Crumb"}) is True

    def test_none_invalid(self):
        assert crumb_rejected({"AAPL": {"price": 185}, "MSFT": {"price": 420}}) is False

    def test_partial_below_threshold_is_false(self):
        # 1/2 = 50%, threshold is "more than 50%", so this is False.
        assert crumb_rejected({"AAPL": "Invalid Crumb", "MSFT": {"price": 420}}) is False

    def test_majority_invalid_is_true(self):
        # 2/3 = 66% > 50% → tripped
        data = {"A": "Invalid Crumb", "B": "Invalid Crumb", "C": {"price": 1}}
        assert crumb_rejected(data) is True

    def test_empty_dict(self):
        assert crumb_rejected({}) is False

    def test_none(self):
        assert crumb_rejected(None) is False


class TestQuotes:
    @pytest.mark.asyncio(loop_scope="function")
    @patch("app.services.yahoo.client.Ticker")
    async def test_empty_symbols(self, mock_ticker_cls):
        result = await yahoo_client.quotes([])
        assert result == []
        mock_ticker_cls.assert_not_called()

    @pytest.mark.asyncio(loop_scope="function")
    @patch("app.services.yahoo.client.Ticker")
    async def test_retries_on_invalid_crumb(self, mock_ticker_cls):
        bad = {"AAPL": "Invalid Crumb"}
        good = {"AAPL": {
            "currency": "USD", "regularMarketPrice": 185.0,
            "regularMarketPreviousClose": 184.0, "regularMarketChange": 1.0,
            "regularMarketChangePercent": 0.005, "regularMarketVolume": 50_000_000,
            "averageDailyVolume10Day": None, "marketState": "REGULAR",
        }}

        ticker1 = MagicMock()
        ticker1.price = bad
        ticker2 = MagicMock()
        ticker2.price = good
        mock_ticker_cls.side_effect = [ticker1, ticker2]

        result = await yahoo_client.quotes(["AAPL"])
        assert len(result) == 1
        assert result[0]["price"] == 185.0
        assert mock_ticker_cls.call_count == 2


class TestCurrencies:
    @pytest.mark.asyncio(loop_scope="function")
    @patch("app.services.yahoo.client.Ticker")
    async def test_empty_symbols(self, mock_ticker_cls):
        assert await yahoo_client.currencies([]) == {}
        mock_ticker_cls.assert_not_called()

    @pytest.mark.asyncio(loop_scope="function")
    @patch("app.services.yahoo.client.Ticker")
    async def test_returns_currency_map(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.price = {
            "AAPL": {"currency": "USD"},
            "HSBA.L": {"currency": "GBp"},
        }
        mock_ticker_cls.return_value = ticker

        result = await yahoo_client.currencies(["AAPL", "HSBA.L"])
        assert result["AAPL"] == "USD"
        assert result["HSBA.L"] == "GBP"

    @pytest.mark.asyncio(loop_scope="function")
    @patch("app.services.yahoo.client.Ticker")
    async def test_non_dict_price_data(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.price = "error"
        mock_ticker_cls.return_value = ticker

        result = await yahoo_client.currencies(["AAPL"])
        assert result["AAPL"] == "USD"

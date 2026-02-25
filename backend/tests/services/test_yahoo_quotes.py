"""Tests for Yahoo Finance real-time quote fetching."""

import math
from unittest.mock import MagicMock, patch

import pytest

from app.services.yahoo.quotes import (
    _has_invalid_crumb,
    _parse_price_data,
    _sanitize,
    batch_fetch_currencies,
    batch_fetch_quotes,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestSanitize:
    def test_none_returns_none(self):
        assert _sanitize(None) is None

    def test_nan_returns_none(self):
        assert _sanitize(float("nan")) is None

    def test_inf_returns_none(self):
        assert _sanitize(float("inf")) is None

    def test_neg_inf_returns_none(self):
        assert _sanitize(float("-inf")) is None

    def test_valid_float_passthrough(self):
        assert _sanitize(42.5) == 42.5

    def test_zero_passthrough(self):
        assert _sanitize(0.0) == 0.0


class TestParsePriceData:
    def test_basic_quote(self):
        ticker = MagicMock()
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

        results = _parse_price_data(ticker, ["AAPL"], price_data)

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
        ticker = MagicMock()
        price_data = {"AAPL": "No data found"}

        results = _parse_price_data(ticker, ["AAPL"], price_data)

        assert len(results) == 1
        assert results[0] == {"symbol": "AAPL"}

    def test_nan_values_sanitized(self):
        ticker = MagicMock()
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

        results = _parse_price_data(ticker, ["AAPL"], price_data)
        q = results[0]
        assert q["price"] is None
        assert q["change"] is None
        assert q["change_percent"] is None

    def test_missing_symbol_in_price_data(self):
        ticker = MagicMock()
        results = _parse_price_data(ticker, ["AAPL"], {})

        assert len(results) == 1
        q = results[0]
        assert q["symbol"] == "AAPL"
        assert q["price"] is None
        assert q["currency"] == "USD"

    def test_currency_normalization_gbp(self):
        ticker = MagicMock()
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

        results = _parse_price_data(ticker, ["HSBA.L"], price_data)
        q = results[0]
        assert q["currency"] == "GBP"
        assert q["price"] == 65.0
        assert q["previous_close"] == 64.0
        assert q["change"] == 1.0

    def test_multiple_symbols(self):
        ticker = MagicMock()
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

        results = _parse_price_data(ticker, ["AAPL", "MSFT"], price_data)
        assert len(results) == 2
        assert results[0]["symbol"] == "AAPL"
        assert results[1]["symbol"] == "MSFT"


class TestHasInvalidCrumb:
    def test_all_invalid(self):
        assert _has_invalid_crumb({"AAPL": "Invalid Crumb", "MSFT": "Invalid Crumb"}) is True

    def test_none_invalid(self):
        assert _has_invalid_crumb({"AAPL": {"price": 185}, "MSFT": {"price": 420}}) is False

    def test_partial_invalid(self):
        assert _has_invalid_crumb({"AAPL": "Invalid Crumb", "MSFT": {"price": 420}}) is False

    def test_empty_dict(self):
        assert _has_invalid_crumb({}) is False


class TestBatchFetchQuotes:
    @patch("app.services.yahoo.quotes.Ticker")
    async def test_empty_symbols(self, mock_ticker_cls):
        result = await batch_fetch_quotes([])
        assert result == []
        mock_ticker_cls.assert_not_called()

    @patch("app.services.yahoo.quotes.Ticker")
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

        result = await batch_fetch_quotes(["AAPL"])
        assert len(result) == 1
        assert result[0]["price"] == 185.0
        assert mock_ticker_cls.call_count == 2


class TestBatchFetchCurrencies:
    @patch("app.services.yahoo.quotes.Ticker")
    def test_empty_symbols(self, mock_ticker_cls):
        assert batch_fetch_currencies([]) == {}

    @patch("app.services.yahoo.quotes.Ticker")
    def test_returns_currency_map(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.price = {
            "AAPL": {"currency": "USD"},
            "HSBA.L": {"currency": "GBp"},
        }
        mock_ticker_cls.return_value = ticker

        result = batch_fetch_currencies(["AAPL", "HSBA.L"])
        assert result["AAPL"] == "USD"
        assert result["HSBA.L"] == "GBP"

    @patch("app.services.yahoo.quotes.Ticker")
    def test_non_dict_price_data(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.price = "error"
        mock_ticker_cls.return_value = ticker

        result = batch_fetch_currencies(["AAPL"])
        assert result["AAPL"] == "USD"

"""Tests for Yahoo Finance symbol validation and type detection."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.yahoo.validation import validate_symbol

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestValidateSymbol:
    @patch("app.services.yahoo.validation.Ticker")
    async def test_valid_us_stock(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"AAPL": {"shortName": "Apple Inc.", "quoteType": "EQUITY"}}
        ticker.price = {"AAPL": {"currency": "USD"}}
        ticker.summary_detail = {"AAPL": {}}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("AAPL")

        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["type"] == "EQUITY"
        assert result["currency"] == "USD"
        assert result["currency_code"] == "USD"

    @patch("app.services.yahoo.validation.Ticker")
    async def test_returns_none_for_invalid_symbol(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"INVALID": None}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("INVALID")
        assert result is None

    @patch("app.services.yahoo.validation.Ticker")
    async def test_returns_none_for_string_error(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"INVALID": "Quote not found for ticker symbol: INVALID"}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("INVALID")
        assert result is None

    @patch("app.services.yahoo.validation.Ticker")
    async def test_etf_type(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"SPY": {"shortName": "SPDR S&P 500", "quoteType": "ETF"}}
        ticker.price = {"SPY": {"currency": "USD"}}
        ticker.summary_detail = {"SPY": {}}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("SPY")
        assert result["type"] == "ETF"

    @patch("app.services.yahoo.validation.Ticker")
    async def test_currency_from_price_info(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"VWCE.DE": {"shortName": "Vanguard FTSE", "quoteType": "ETF"}}
        ticker.price = {"VWCE.DE": {"currency": "EUR"}}
        ticker.summary_detail = {"VWCE.DE": {}}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("VWCE.DE")
        assert result["currency"] == "EUR"
        assert result["currency_code"] == "EUR"

    @patch("app.services.yahoo.validation.Ticker")
    async def test_currency_fallback_to_summary_detail(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"AAPL": {"shortName": "Apple", "quoteType": "EQUITY"}}
        ticker.price = {"AAPL": {}}  # No currency in price
        ticker.summary_detail = {"AAPL": {"currency": "USD"}}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("AAPL")
        assert result["currency"] == "USD"

    @patch("app.services.yahoo.validation.Ticker")
    async def test_currency_fallback_to_suffix(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"006260.KS": {"shortName": "LS Corp", "quoteType": "EQUITY"}}
        ticker.price = {"006260.KS": {}}
        ticker.summary_detail = {"006260.KS": {}}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("006260.KS")
        assert result["currency"] == "KRW"
        assert result["currency_code"] == "KRW"

    @patch("app.services.yahoo.validation.Ticker")
    async def test_currency_fallback_to_usd(self, mock_ticker_cls):
        """US stocks with no currency info anywhere default to USD."""
        ticker = MagicMock()
        ticker.quote_type = {"AAPL": {"shortName": "Apple", "quoteType": "EQUITY"}}
        ticker.price = {"AAPL": {}}
        ticker.summary_detail = {"AAPL": {}}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("AAPL")
        assert result["currency_code"] == "USD"

    @patch("app.services.yahoo.validation.Ticker")
    async def test_name_fallback_to_longname(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"AAPL": {"longName": "Apple Inc.", "quoteType": "EQUITY"}}
        ticker.price = {"AAPL": {"currency": "USD"}}
        ticker.summary_detail = {"AAPL": {}}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("AAPL")
        assert result["name"] == "Apple Inc."

    @patch("app.services.yahoo.validation.Ticker")
    async def test_name_fallback_to_symbol(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"AAPL": {"quoteType": "EQUITY"}}
        ticker.price = {"AAPL": {"currency": "USD"}}
        ticker.summary_detail = {"AAPL": {}}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("AAPL")
        assert result["name"] == "AAPL"

    @patch("app.services.yahoo.validation.Ticker")
    async def test_gbp_subunit_normalization(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"HSBA.L": {"shortName": "HSBC Holdings", "quoteType": "EQUITY"}}
        ticker.price = {"HSBA.L": {"currency": "GBp"}}
        ticker.summary_detail = {"HSBA.L": {}}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("HSBA.L")
        assert result["currency"] == "GBP"
        assert result["currency_code"] == "GBp"

    @patch("app.services.yahoo.validation.Ticker")
    async def test_non_dict_price_info_uses_suffix(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"7203.T": {"shortName": "Toyota", "quoteType": "EQUITY"}}
        ticker.price = {"7203.T": "No data found"}
        ticker.summary_detail = {"7203.T": "No data found"}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("7203.T")
        assert result["currency"] == "JPY"

    @patch("app.services.yahoo.validation.Ticker")
    async def test_symbol_uppercased(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.quote_type = {"aapl": {"shortName": "Apple", "quoteType": "EQUITY"}}
        ticker.price = {"aapl": {"currency": "USD"}}
        ticker.summary_detail = {"aapl": {}}
        mock_ticker_cls.return_value = ticker

        result = await validate_symbol("aapl")
        assert result["symbol"] == "AAPL"

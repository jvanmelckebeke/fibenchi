"""Tests for Yahoo Finance fundamental metrics fetching."""

import math
from unittest.mock import MagicMock, patch

import pytest

from app.services.yahoo.fundamentals import (
    FUNDAMENTAL_FIELDS,
    _batch_fetch_fundamentals_sync,
    _safe_float,
    batch_fetch_fundamentals,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestSafeFloat:
    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_nan_returns_none(self):
        assert _safe_float(float("nan")) is None

    def test_inf_returns_none(self):
        assert _safe_float(float("inf")) is None

    def test_neg_inf_returns_none(self):
        assert _safe_float(float("-inf")) is None

    def test_valid_float(self):
        assert _safe_float(15.678, multiplier=1, decimals=2) == 15.68

    def test_multiplier_applied(self):
        assert _safe_float(0.15, multiplier=100, decimals=1) == 15.0

    def test_string_number_converted(self):
        assert _safe_float("42.5", multiplier=1, decimals=1) == 42.5

    def test_invalid_string_returns_none(self):
        assert _safe_float("not_a_number") is None

    def test_zero_value(self):
        assert _safe_float(0.0) == 0.0

    def test_negative_value(self):
        assert _safe_float(-5.5, multiplier=1, decimals=1) == -5.5


class TestFundamentalFields:
    def test_expected_fields_exist(self):
        expected = {"forward_pe", "peg_ratio", "roe", "ev_ebitda", "revenue_growth"}
        assert set(FUNDAMENTAL_FIELDS.keys()) == expected

    def test_roe_has_100x_multiplier(self):
        _, _, _, multiplier = FUNDAMENTAL_FIELDS["roe"]
        assert multiplier == 100

    def test_revenue_growth_has_100x_multiplier(self):
        _, _, _, multiplier = FUNDAMENTAL_FIELDS["revenue_growth"]
        assert multiplier == 100

    def test_forward_pe_has_1x_multiplier(self):
        _, _, _, multiplier = FUNDAMENTAL_FIELDS["forward_pe"]
        assert multiplier == 1


class TestBatchFetchFundamentalsSync:
    @patch("app.services.yahoo.fundamentals.Ticker")
    def test_empty_symbols(self, mock_ticker_cls):
        assert _batch_fetch_fundamentals_sync([]) == {}

    @patch("app.services.yahoo.fundamentals.Ticker")
    def test_returns_all_fields(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.key_stats = {
            "AAPL": {"forwardPE": 28.5, "pegRatio": 2.1, "enterpriseToEbitda": 22.3}
        }
        ticker.financial_data = {
            "AAPL": {"returnOnEquity": 0.157, "revenueGrowth": 0.089}
        }
        mock_ticker_cls.return_value = ticker

        result = _batch_fetch_fundamentals_sync(["AAPL"])

        assert "AAPL" in result
        data = result["AAPL"]
        assert data["forward_pe"] == 28.5
        assert data["peg_ratio"] == 2.1
        assert data["roe"] == 15.7
        assert data["ev_ebitda"] == 22.3
        assert data["revenue_growth"] == 8.9

    @patch("app.services.yahoo.fundamentals.Ticker")
    def test_missing_fields_are_none(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.key_stats = {"AAPL": {"forwardPE": 28.5}}
        ticker.financial_data = {"AAPL": {}}
        mock_ticker_cls.return_value = ticker

        result = _batch_fetch_fundamentals_sync(["AAPL"])
        data = result["AAPL"]
        assert data["forward_pe"] == 28.5
        assert data["roe"] is None
        assert data["revenue_growth"] is None

    @patch("app.services.yahoo.fundamentals.Ticker")
    def test_string_error_for_symbol(self, mock_ticker_cls):
        """Yahoo returns string errors for symbols with no data."""
        ticker = MagicMock()
        ticker.key_stats = {"AAPL": "No fundamentals data found"}
        ticker.financial_data = {"AAPL": "No fundamentals data found"}
        mock_ticker_cls.return_value = ticker

        result = _batch_fetch_fundamentals_sync(["AAPL"])
        data = result["AAPL"]
        assert all(v is None for v in data.values())

    @patch("app.services.yahoo.fundamentals.Ticker")
    def test_nan_values_filtered(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.key_stats = {"AAPL": {"forwardPE": float("nan"), "pegRatio": float("inf")}}
        ticker.financial_data = {"AAPL": {}}
        mock_ticker_cls.return_value = ticker

        result = _batch_fetch_fundamentals_sync(["AAPL"])
        assert result["AAPL"]["forward_pe"] is None
        assert result["AAPL"]["peg_ratio"] is None

    @patch("app.services.yahoo.fundamentals.Ticker")
    def test_multiple_symbols(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.key_stats = {
            "AAPL": {"forwardPE": 28.5, "pegRatio": 2.1, "enterpriseToEbitda": 22.3},
            "MSFT": {"forwardPE": 32.0, "pegRatio": 1.8, "enterpriseToEbitda": 25.0},
        }
        ticker.financial_data = {
            "AAPL": {"returnOnEquity": 0.15, "revenueGrowth": 0.08},
            "MSFT": {"returnOnEquity": 0.38, "revenueGrowth": 0.15},
        }
        mock_ticker_cls.return_value = ticker

        result = _batch_fetch_fundamentals_sync(["AAPL", "MSFT"])
        assert len(result) == 2
        assert result["MSFT"]["roe"] == 38.0
        assert result["MSFT"]["revenue_growth"] == 15.0


class TestBatchFetchFundamentalsAsync:
    @patch("app.services.yahoo.fundamentals.Ticker")
    async def test_async_wrapper(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.key_stats = {"AAPL": {"forwardPE": 28.5}}
        ticker.financial_data = {"AAPL": {"returnOnEquity": 0.15}}
        mock_ticker_cls.return_value = ticker

        result = await batch_fetch_fundamentals(["AAPL"])
        assert result["AAPL"]["forward_pe"] == 28.5

    @patch("app.services.yahoo.fundamentals.Ticker")
    async def test_empty_returns_empty(self, mock_ticker_cls):
        result = await batch_fetch_fundamentals([])
        assert result == {}

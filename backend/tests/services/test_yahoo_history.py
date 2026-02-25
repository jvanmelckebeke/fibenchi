"""Tests for Yahoo Finance OHLCV history fetching."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.services.yahoo.history import (
    PERIOD_MAP,
    _batch_fetch_history_sync,
    fetch_history,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


def _make_ohlcv_df(n: int = 5, base: float = 100.0) -> pd.DataFrame:
    """Create a simple OHLCV DataFrame like Yahoo returns."""
    dates = pd.bdate_range(end=date.today(), periods=n)
    return pd.DataFrame(
        {
            "open": [base + i for i in range(n)],
            "high": [base + i + 1 for i in range(n)],
            "low": [base + i - 1 for i in range(n)],
            "close": [base + i + 0.5 for i in range(n)],
            "volume": [1_000_000] * n,
        },
        index=dates,
    )


def _make_multi_index_df(symbols: list[str], n: int = 5, base: float = 100.0) -> pd.DataFrame:
    """Create a MultiIndex OHLCV DataFrame (multi-symbol batch result)."""
    frames = []
    dates = pd.bdate_range(end=date.today(), periods=n)
    for sym in symbols:
        df = pd.DataFrame(
            {
                "open": [base + i for i in range(n)],
                "high": [base + i + 1 for i in range(n)],
                "low": [base + i - 1 for i in range(n)],
                "close": [base + i + 0.5 for i in range(n)],
                "volume": [1_000_000] * n,
            },
            index=pd.MultiIndex.from_tuples(
                [(sym, d) for d in dates], names=["symbol", "date"]
            ),
        )
        frames.append(df)
    return pd.concat(frames)


class TestFetchHistory:
    """Tests for the single-symbol fetch_history function."""

    @patch("app.services.yahoo.history.Ticker")
    async def test_returns_dataframe_with_period(self, mock_ticker_cls):
        df = _make_ohlcv_df()
        ticker = MagicMock()
        ticker.history.return_value = df
        ticker.price = {"AAPL": {"currency": "USD"}}
        mock_ticker_cls.return_value = ticker

        result = await fetch_history("AAPL", period="3mo")

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]
        ticker.history.assert_called_once_with(period="3mo", interval="1d")

    @patch("app.services.yahoo.history.Ticker")
    async def test_uses_start_end_when_provided(self, mock_ticker_cls):
        df = _make_ohlcv_df()
        ticker = MagicMock()
        ticker.history.return_value = df
        ticker.price = {"AAPL": {"currency": "USD"}}
        mock_ticker_cls.return_value = ticker

        s, e = date(2025, 1, 1), date(2025, 3, 1)
        await fetch_history("AAPL", start=s, end=e)

        ticker.history.assert_called_once_with(
            start="2025-01-01", end="2025-03-01", interval="1d"
        )

    @patch("app.services.yahoo.history.Ticker")
    async def test_raises_on_empty_dataframe(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = ticker

        with pytest.raises(ValueError, match="No data found"):
            await fetch_history("INVALID")

    @patch("app.services.yahoo.history.Ticker")
    async def test_raises_on_dict_response(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.history.return_value = {"INVALID": "No data found"}
        mock_ticker_cls.return_value = ticker

        with pytest.raises(ValueError, match="No data found"):
            await fetch_history("INVALID")

    @patch("app.services.yahoo.history.Ticker")
    async def test_handles_multi_index(self, mock_ticker_cls):
        """Yahoo sometimes returns MultiIndex even for single symbols."""
        dates = pd.bdate_range(end=date.today(), periods=3)
        df = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [101, 102, 103],
                "low": [99, 100, 101],
                "close": [100.5, 101.5, 102.5],
                "volume": [1_000_000, 1_000_000, 1_000_000],
            },
            index=pd.MultiIndex.from_tuples(
                [("AAPL", d) for d in dates], names=["symbol", "date"]
            ),
        )
        ticker = MagicMock()
        ticker.history.return_value = df
        ticker.price = {"AAPL": {"currency": "USD"}}
        mock_ticker_cls.return_value = ticker

        result = await fetch_history("AAPL")
        assert result.index.name == "date"

    @patch("app.services.yahoo.history.Ticker")
    async def test_applies_currency_divisor(self, mock_ticker_cls):
        """GBp prices should be divided by 100."""
        df = pd.DataFrame(
            {
                "open": [15000.0],
                "high": [15100.0],
                "low": [14900.0],
                "close": [15050.0],
                "volume": [500_000],
            },
            index=pd.DatetimeIndex([date.today()]),
        )
        ticker = MagicMock()
        ticker.history.return_value = df
        ticker.price = {"HSBA.L": {"currency": "GBp"}}
        mock_ticker_cls.return_value = ticker

        result = await fetch_history("HSBA.L")
        assert result["close"].iloc[0] == 150.50

    @patch("app.services.yahoo.history.Ticker")
    async def test_normalizes_period_alias(self, mock_ticker_cls):
        """'1w' should map to '5d'."""
        df = _make_ohlcv_df()
        ticker = MagicMock()
        ticker.history.return_value = df
        ticker.price = {"AAPL": {"currency": "USD"}}
        mock_ticker_cls.return_value = ticker

        await fetch_history("AAPL", period="1w")
        ticker.history.assert_called_once_with(period="5d", interval="1d")


class TestPeriodMap:
    def test_contains_expected_keys(self):
        expected = {"1d", "5d", "1w", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"}
        assert set(PERIOD_MAP.keys()) == expected

    def test_1w_maps_to_5d(self):
        assert PERIOD_MAP["1w"] == "5d"


class TestBatchFetchHistorySync:
    @patch("app.services.yahoo.history.Ticker")
    def test_empty_symbols_returns_empty(self, mock_ticker_cls):
        assert _batch_fetch_history_sync([]) == {}

    @patch("app.services.yahoo.history.Ticker")
    def test_empty_history_returns_empty(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.history.return_value = pd.DataFrame()
        ticker.price = {}
        mock_ticker_cls.return_value = ticker

        assert _batch_fetch_history_sync(["AAPL"]) == {}

    @patch("app.services.yahoo.history.Ticker")
    def test_dict_history_returns_empty(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.history.return_value = {"error": "no data"}
        ticker.price = {}
        mock_ticker_cls.return_value = ticker

        assert _batch_fetch_history_sync(["AAPL"]) == {}

    @patch("app.services.yahoo.history.Ticker")
    def test_returns_dataframes_per_symbol(self, mock_ticker_cls):
        df = _make_multi_index_df(["AAPL", "MSFT"], n=5)
        ticker = MagicMock()
        ticker.history.return_value = df
        ticker.price = {
            "AAPL": {"currency": "USD"},
            "MSFT": {"currency": "USD"},
        }
        mock_ticker_cls.return_value = ticker

        result = _batch_fetch_history_sync(["AAPL", "MSFT"])
        assert "AAPL" in result
        assert "MSFT" in result
        assert len(result["AAPL"]) == 5

    @patch("app.services.yahoo.history.Ticker")
    def test_skips_symbol_with_too_few_rows(self, mock_ticker_cls):
        """Symbols with < 2 rows are skipped."""
        dates = pd.bdate_range(end=date.today(), periods=1)
        df = pd.DataFrame(
            {"open": [100], "high": [101], "low": [99], "close": [100.5], "volume": [1_000_000]},
            index=pd.MultiIndex.from_tuples([("AAPL", dates[0])], names=["symbol", "date"]),
        )
        ticker = MagicMock()
        ticker.history.return_value = df
        ticker.price = {"AAPL": {"currency": "USD"}}
        mock_ticker_cls.return_value = ticker

        result = _batch_fetch_history_sync(["AAPL"])
        assert result == {}

    @patch("app.services.yahoo.history.Ticker")
    def test_skips_missing_symbol_keyerror(self, mock_ticker_cls):
        """Gracefully skip symbols that raise KeyError on .loc."""
        dates = pd.bdate_range(end=date.today(), periods=3)
        df = pd.DataFrame(
            {"open": [100, 101, 102], "high": [101, 102, 103], "low": [99, 100, 101],
             "close": [100.5, 101.5, 102.5], "volume": [1_000_000] * 3},
            index=pd.MultiIndex.from_tuples(
                [("AAPL", d) for d in dates], names=["symbol", "date"]
            ),
        )
        ticker = MagicMock()
        ticker.history.return_value = df
        ticker.price = {"AAPL": {"currency": "USD"}}
        mock_ticker_cls.return_value = ticker

        result = _batch_fetch_history_sync(["AAPL", "MISSING"])
        assert "AAPL" in result
        assert "MISSING" not in result

    @patch("app.services.yahoo.history.Ticker")
    def test_applies_currency_normalization(self, mock_ticker_cls):
        """GBp prices in batch should be divided by 100."""
        dates = pd.bdate_range(end=date.today(), periods=3)
        df = pd.DataFrame(
            {"open": [15000, 15100, 15200], "high": [15100, 15200, 15300],
             "low": [14900, 15000, 15100], "close": [15050, 15150, 15250],
             "volume": [500_000] * 3},
            index=pd.MultiIndex.from_tuples(
                [("HSBA.L", d) for d in dates], names=["symbol", "date"]
            ),
        )
        ticker = MagicMock()
        ticker.history.return_value = df
        ticker.price = {"HSBA.L": {"currency": "GBp"}}
        mock_ticker_cls.return_value = ticker

        result = _batch_fetch_history_sync(["HSBA.L"])
        assert "HSBA.L" in result
        assert result["HSBA.L"]["close"].iloc[0] == 150.50

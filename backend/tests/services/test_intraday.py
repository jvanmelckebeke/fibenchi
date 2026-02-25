"""Tests for intraday price fetching and session classification."""

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.services.intraday import (
    _EXCHANGE_HOURS,
    _classify_session,
    _fetch_intraday_sync,
    fetch_and_store_intraday,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")

ET = ZoneInfo("America/New_York")
CPH = ZoneInfo("Europe/Copenhagen")

# Access the unwrapped sync function for direct unit testing
# (the @async_threadable decorator preserves __wrapped__)
_fetch_intraday_sync_inner = _fetch_intraday_sync.__wrapped__


# ---------- _classify_session ----------


class TestClassifySession:
    """Session classification logic for pre/regular/post."""

    def test_us_premarket(self):
        ts = datetime(2026, 2, 25, 7, 0, tzinfo=ET)
        assert _classify_session(ts, "America/New_York") == "pre"

    def test_us_regular(self):
        ts = datetime(2026, 2, 25, 10, 0, tzinfo=ET)
        assert _classify_session(ts, "America/New_York") == "regular"

    def test_us_regular_at_open(self):
        ts = datetime(2026, 2, 25, 9, 30, tzinfo=ET)
        assert _classify_session(ts, "America/New_York") == "regular"

    def test_us_post_at_close(self):
        ts = datetime(2026, 2, 25, 16, 0, tzinfo=ET)
        assert _classify_session(ts, "America/New_York") == "post"

    def test_us_postmarket(self):
        ts = datetime(2026, 2, 25, 18, 0, tzinfo=ET)
        assert _classify_session(ts, "America/New_York") == "post"

    def test_copenhagen_regular(self):
        """NKT.CO: 10:00 CET is regular Copenhagen hours (9:00-17:00)."""
        ts = datetime(2026, 2, 25, 10, 0, tzinfo=CPH)
        assert _classify_session(ts, "Europe/Copenhagen") == "regular"

    def test_copenhagen_pre(self):
        """NKT.CO: 8:30 CET is before Copenhagen open (9:00)."""
        ts = datetime(2026, 2, 25, 8, 30, tzinfo=CPH)
        assert _classify_session(ts, "Europe/Copenhagen") == "pre"

    def test_copenhagen_post(self):
        ts = datetime(2026, 2, 25, 17, 0, tzinfo=CPH)
        assert _classify_session(ts, "Europe/Copenhagen") == "post"

    def test_copenhagen_fallback_to_et_misclassifies(self):
        """Without timezone info, 10:00 CET falls back to ET (4:00 AM) → 'pre'.

        This documents the bug that the tz_name extraction fixes.
        """
        ts = datetime(2026, 2, 25, 10, 0, tzinfo=CPH)
        assert _classify_session(ts, None) == "pre"  # wrong! should be regular

    def test_unknown_timezone_falls_back_to_et(self):
        ts = datetime(2026, 2, 25, 10, 0, tzinfo=ET)
        assert _classify_session(ts, "Unknown/Timezone") == "regular"

    def test_london_regular(self):
        ts = datetime(2026, 2, 25, 12, 0, tzinfo=ZoneInfo("Europe/London"))
        assert _classify_session(ts, "Europe/London") == "regular"

    def test_london_pre(self):
        ts = datetime(2026, 2, 25, 7, 30, tzinfo=ZoneInfo("Europe/London"))
        assert _classify_session(ts, "Europe/London") == "pre"


# ---------- _EXCHANGE_HOURS completeness ----------


class TestExchangeHours:
    """Verify key exchanges are present in the lookup."""

    @pytest.mark.parametrize("tz", [
        "Europe/Copenhagen",
        "Europe/Oslo",
        "Europe/Brussels",
        "Europe/Dublin",
        "Europe/Lisbon",
        "Europe/Warsaw",
        "Europe/Athens",
        "Europe/Istanbul",
    ])
    def test_newly_added_timezones_present(self, tz):
        assert tz in _EXCHANGE_HOURS

    @pytest.mark.parametrize("tz", [
        "America/New_York",
        "Europe/London",
        "Europe/Berlin",
        "Europe/Stockholm",
        "Asia/Tokyo",
        "Australia/Sydney",
    ])
    def test_core_timezones_present(self, tz):
        assert tz in _EXCHANGE_HOURS

    def test_hours_are_time_tuples(self):
        for tz, (open_t, close_t) in _EXCHANGE_HOURS.items():
            assert isinstance(open_t, time), f"{tz} open is not a time"
            assert isinstance(close_t, time), f"{tz} close is not a time"
            assert open_t < close_t, f"{tz} open >= close"


# ---------- _fetch_intraday_sync ----------


def _make_hist_df(sym: str, timestamps: list[datetime], prices: list[float]) -> pd.DataFrame:
    """Build a DataFrame mimicking yahooquery multi-symbol history output."""
    data = {
        "close": prices,
        "open": prices,
        "high": prices,
        "low": prices,
        "volume": [1000] * len(prices),
    }
    idx = pd.DatetimeIndex(timestamps)
    mi = pd.MultiIndex.from_arrays(
        [[sym] * len(timestamps), idx],
        names=["symbol", "date"],
    )
    return pd.DataFrame(data, index=mi)


class TestFetchIntradaySync:
    """Tests for _fetch_intraday_sync — timezone extraction and includePrePost.

    Uses __wrapped__ to call the underlying sync function directly.
    """

    def test_extracts_timezone_from_timestamps(self):
        """When Yahoo returns exchangeTimezoneName=None, tz is extracted from bar timestamps."""
        ts_list = [
            datetime(2026, 2, 25, 9, 0, tzinfo=CPH),
            datetime(2026, 2, 25, 10, 0, tzinfo=CPH),
            datetime(2026, 2, 25, 11, 0, tzinfo=CPH),
        ]
        hist = _make_hist_df("NKT.CO", ts_list, [100.0, 101.0, 102.0])

        price_data = {"NKT.CO": {
            "currency": "DKK",
            "exchangeTimezoneName": None,  # Yahoo returns None for Copenhagen
        }}

        mock_ticker = MagicMock()
        mock_ticker.price = price_data
        mock_ticker._get_data.return_value = {}
        mock_ticker._historical_data_to_dataframe.return_value = hist

        with patch("app.services.intraday.Ticker", return_value=mock_ticker):
            result = _fetch_intraday_sync_inner(["NKT.CO"])

        assert "NKT.CO" in result
        sessions = {bar["session"] for bar in result["NKT.CO"]}
        # All bars 9:00-11:00 CET are within Copenhagen regular hours
        assert sessions == {"regular"}

    def test_us_premarket_bars_classified_as_pre(self):
        """Premarket bars for US stocks should be classified as 'pre'."""
        ts_list = [
            datetime(2026, 2, 25, 4, 0, tzinfo=ET),
            datetime(2026, 2, 25, 5, 0, tzinfo=ET),
            datetime(2026, 2, 25, 7, 0, tzinfo=ET),
        ]
        hist = _make_hist_df("KTOS", ts_list, [30.0, 30.5, 31.0])

        price_data = {"KTOS": {
            "currency": "USD",
            "exchangeTimezoneName": "America/New_York",
        }}

        mock_ticker = MagicMock()
        mock_ticker.price = price_data
        mock_ticker._get_data.return_value = {}
        mock_ticker._historical_data_to_dataframe.return_value = hist

        with patch("app.services.intraday.Ticker", return_value=mock_ticker):
            result = _fetch_intraday_sync_inner(["KTOS"])

        assert "KTOS" in result
        sessions = {bar["session"] for bar in result["KTOS"]}
        assert sessions == {"pre"}

    def test_mixed_sessions_us(self):
        """Bars spanning pre → regular → post get different session labels."""
        ts_list = [
            datetime(2026, 2, 25, 8, 0, tzinfo=ET),   # pre
            datetime(2026, 2, 25, 10, 0, tzinfo=ET),  # regular
            datetime(2026, 2, 25, 17, 0, tzinfo=ET),  # post
        ]
        hist = _make_hist_df("AAPL", ts_list, [180.0, 181.0, 180.5])

        price_data = {"AAPL": {
            "currency": "USD",
            "exchangeTimezoneName": "America/New_York",
        }}

        mock_ticker = MagicMock()
        mock_ticker.price = price_data
        mock_ticker._get_data.return_value = {}
        mock_ticker._historical_data_to_dataframe.return_value = hist

        with patch("app.services.intraday.Ticker", return_value=mock_ticker):
            result = _fetch_intraday_sync_inner(["AAPL"])

        sessions = [bar["session"] for bar in result["AAPL"]]
        assert sessions == ["pre", "regular", "post"]

    def test_calls_get_data_with_include_prepost(self):
        """Verify the Yahoo API call includes includePrePost=true."""
        hist = _make_hist_df("KTOS", [], [])

        mock_ticker = MagicMock()
        mock_ticker.price = {}
        mock_ticker._get_data.return_value = {}
        mock_ticker._historical_data_to_dataframe.return_value = hist

        with patch("app.services.intraday.Ticker", return_value=mock_ticker):
            _fetch_intraday_sync_inner(["KTOS"])

        mock_ticker._get_data.assert_called_once_with(
            "chart",
            {"range": "1d", "interval": "1m", "includePrePost": "true"},
        )

    def test_empty_symbols_returns_empty(self):
        assert _fetch_intraday_sync_inner([]) == {}

    def test_applies_currency_divisor(self):
        """Subunit currencies (e.g. GBp) should divide prices."""
        ts_list = [datetime(2026, 2, 25, 10, 0, tzinfo=ZoneInfo("Europe/London"))]
        hist = _make_hist_df("VOD.L", ts_list, [8500.0])

        price_data = {"VOD.L": {
            "currency": "GBp",
            "exchangeTimezoneName": "Europe/London",
        }}

        mock_ticker = MagicMock()
        mock_ticker.price = price_data
        mock_ticker._get_data.return_value = {}
        mock_ticker._historical_data_to_dataframe.return_value = hist

        with patch("app.services.intraday.Ticker", return_value=mock_ticker):
            with patch("app.services.intraday.resolve_currency", return_value=("GBP", 100)):
                result = _fetch_intraday_sync_inner(["VOD.L"])

        assert result["VOD.L"][0]["price"] == 85.0

    def test_filters_synthetic_non_minute_boundary_bars(self):
        """Yahoo echo bars at non-minute-boundary timestamps are dropped."""
        ts_list = [
            datetime(2026, 2, 25, 10, 0, 0, tzinfo=CPH),   # real: on minute
            datetime(2026, 2, 25, 10, 3, 43, tzinfo=CPH),   # synthetic: 43s offset
            datetime(2026, 2, 25, 10, 5, 0, tzinfo=CPH),    # real: on minute
        ]
        hist = _make_hist_df("P911.DE", ts_list, [41.0, 41.75, 42.0])

        price_data = {"P911.DE": {
            "currency": "EUR",
            "exchangeTimezoneName": "Europe/Berlin",
        }}

        mock_ticker = MagicMock()
        mock_ticker.price = price_data
        mock_ticker._get_data.return_value = {}
        mock_ticker._historical_data_to_dataframe.return_value = hist

        with patch("app.services.intraday.Ticker", return_value=mock_ticker):
            result = _fetch_intraday_sync_inner(["P911.DE"])

        assert "P911.DE" in result
        assert len(result["P911.DE"]) == 2  # synthetic bar dropped
        prices = [bar["price"] for bar in result["P911.DE"]]
        assert prices == [41.0, 42.0]

    def test_skips_symbol_on_key_error(self):
        """Symbols missing from the DataFrame are silently skipped."""
        hist = _make_hist_df("AAPL", [datetime(2026, 2, 25, 10, 0, tzinfo=ET)], [180.0])

        mock_ticker = MagicMock()
        mock_ticker.price = {"AAPL": {"currency": "USD", "exchangeTimezoneName": "America/New_York"}}
        mock_ticker._get_data.return_value = {}
        mock_ticker._historical_data_to_dataframe.return_value = hist

        with patch("app.services.intraday.Ticker", return_value=mock_ticker):
            result = _fetch_intraday_sync_inner(["AAPL", "MISSING"])

        assert "AAPL" in result
        assert "MISSING" not in result


# ---------- fetch_and_store_intraday ----------


class TestFetchAndStoreIntraday:
    """Tests for DB storage: stale-bar cleanup and upsert."""

    async def test_deletes_stale_bars_before_upsert(self):
        """Bars older than the oldest fresh bar should be deleted."""
        fresh_bars = [
            {"timestamp": datetime(2026, 2, 25, 9, 0, tzinfo=ET), "price": 30.0, "volume": 100, "session": "regular"},
            {"timestamp": datetime(2026, 2, 25, 10, 0, tzinfo=ET), "price": 31.0, "volume": 200, "session": "regular"},
        ]

        mock_db = AsyncMock()

        with patch("app.services.intraday._fetch_intraday_sync", new_callable=AsyncMock, return_value={"KTOS": fresh_bars}):
            count = await fetch_and_store_intraday(mock_db, ["KTOS"], {"KTOS": 1})

        assert count == 2

        # Should have 2 execute calls: 1 delete + 1 upsert
        calls = mock_db.execute.call_args_list
        assert len(calls) == 2

        # First call is the delete for stale bars
        delete_sql = str(calls[0].args[0])
        assert "DELETE" in delete_sql.upper()

    async def test_no_data_returns_zero(self):
        mock_db = AsyncMock()

        with patch("app.services.intraday._fetch_intraday_sync", new_callable=AsyncMock, return_value={}):
            count = await fetch_and_store_intraday(mock_db, ["KTOS"], {"KTOS": 1})

        assert count == 0
        mock_db.execute.assert_not_called()

    async def test_skips_unknown_symbols(self):
        """Bars for symbols not in asset_map are skipped."""
        fresh_bars = [
            {"timestamp": datetime(2026, 2, 25, 9, 0, tzinfo=ET), "price": 30.0, "volume": 100, "session": "regular"},
        ]
        mock_db = AsyncMock()

        with patch("app.services.intraday._fetch_intraday_sync", new_callable=AsyncMock, return_value={"UNKNOWN": fresh_bars}):
            count = await fetch_and_store_intraday(mock_db, ["UNKNOWN"], {"KTOS": 1})

        assert count == 0

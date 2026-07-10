"""Tests for Yahoo Finance earnings date fetching."""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.yahoo import yahoo_client
from app.services.yahoo._parsers import (
    last_reported_date as _extract_last_reported_date,
)
from app.services.yahoo._parsers import (
    parse_earnings_date as _parse_earnings_date,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestParseEarningsDate:
    async def test_standard_format(self):
        assert _parse_earnings_date("2026-04-30 16:30:S") == datetime.date(2026, 4, 30)

    async def test_date_only(self):
        assert _parse_earnings_date("2026-04-30") == datetime.date(2026, 4, 30)

    async def test_none(self):
        assert _parse_earnings_date(None) is None

    async def test_empty_string(self):
        assert _parse_earnings_date("") is None

    async def test_invalid(self):
        assert _parse_earnings_date("not-a-date") is None


class TestExtractLastReportedDate:
    async def test_picks_most_recent(self):
        data = {
            "earningsChart": {
                "quarterly": [
                    {"date": "1Q2025", "reportedDate": 1746735000},
                    {"date": "2Q2025", "reportedDate": 1754598163},
                    {"date": "4Q2025", "reportedDate": 1772141075},
                    {"date": "3Q2025", "reportedDate": 1762463400},
                ]
            }
        }
        result = _extract_last_reported_date(data)
        assert result == datetime.date.fromtimestamp(1772141075)

    async def test_empty_quarterly(self):
        assert _extract_last_reported_date({"earningsChart": {"quarterly": []}}) is None

    async def test_missing_chart(self):
        assert _extract_last_reported_date({}) is None

    async def test_no_reported_date_field(self):
        data = {"earningsChart": {"quarterly": [{"date": "1Q2025"}]}}
        assert _extract_last_reported_date(data) is None


class TestFetchEarningsDate:
    @patch("app.services.yahoo.client.Ticker")
    async def test_confirmed_date_with_reported(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.calendar_events = {
            "AAPL": {
                "earnings": {
                    "earningsDate": ["2026-04-30 16:30:S"],
                    "isEarningsDateEstimate": False,
                }
            }
        }
        ticker.earnings = {
            "AAPL": {
                "earningsChart": {
                    "quarterly": [
                        {"date": "4Q2025", "reportedDate": 1772141075},
                    ]
                }
            }
        }
        mock_ticker_cls.return_value = ticker

        result = await yahoo_client.earnings("AAPL")
        assert result is not None
        assert result["earnings_date"] == datetime.date(2026, 4, 30)
        assert result["is_estimate"] is False
        assert result["last_reported_date"] == datetime.date.fromtimestamp(1772141075)

    @patch("app.services.yahoo.client.Ticker")
    async def test_estimated_date(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.calendar_events = {
            "TSLA": {
                "earnings": {
                    "earningsDate": ["2026-07-15"],
                    "isEarningsDateEstimate": True,
                }
            }
        }
        ticker.earnings = {"TSLA": {}}
        mock_ticker_cls.return_value = ticker

        result = await yahoo_client.earnings("TSLA")
        assert result is not None
        assert result["earnings_date"] == datetime.date(2026, 7, 15)
        assert result["is_estimate"] is True
        assert result["last_reported_date"] is None

    @patch("app.services.yahoo.client.Ticker")
    async def test_no_data_returns_none(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.calendar_events = {"AAPL": "No data found"}
        mock_ticker_cls.return_value = ticker

        assert await yahoo_client.earnings("AAPL") is None

    @patch("app.services.yahoo.client.Ticker")
    async def test_string_error_returns_none(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.calendar_events = "No fundamentals data found"
        mock_ticker_cls.return_value = ticker

        assert await yahoo_client.earnings("AAPL") is None

    @patch("app.services.yahoo.client.Ticker")
    async def test_empty_earnings_list_returns_none(self, mock_ticker_cls):
        ticker = MagicMock()
        ticker.calendar_events = {
            "AAPL": {
                "earnings": {
                    "earningsDate": [],
                }
            }
        }
        mock_ticker_cls.return_value = ticker

        assert await yahoo_client.earnings("AAPL") is None

    @patch("app.services.yahoo.client.Ticker")
    async def test_earnings_history_error_still_returns_next_date(self, mock_ticker_cls):
        """If ticker.earnings raises, we still get the next date."""
        ticker = MagicMock()
        ticker.calendar_events = {
            "AAPL": {
                "earnings": {
                    "earningsDate": ["2026-04-30"],
                    "isEarningsDateEstimate": True,
                }
            }
        }
        ticker.earnings = "No data found"  # string error
        mock_ticker_cls.return_value = ticker

        result = await yahoo_client.earnings("AAPL")
        assert result is not None
        assert result["earnings_date"] == datetime.date(2026, 4, 30)
        assert result["last_reported_date"] is None

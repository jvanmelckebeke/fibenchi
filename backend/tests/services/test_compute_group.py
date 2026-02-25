"""Tests for batch indicator computation and sparkline data (group.py)."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.compute.group import (
    _indicator_cache,
    compute_and_cache_indicators,
    get_batch_sparklines,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


def _make_asset_row(id: int, symbol: str):
    """Create a mock asset row with .id and .symbol attributes."""
    row = MagicMock()
    row.id = id
    row.symbol = symbol
    return row


def _make_price(asset_id: int, d: date, close: float):
    """Create a mock PriceHistory object."""
    p = MagicMock()
    p.asset_id = asset_id
    p.date = d
    p.close = close
    p.open = close - 0.5
    p.high = close + 1.0
    p.low = close - 1.0
    p.volume = 1_000_000
    return p


def _mock_merge_fundamentals(fund_data: dict):
    """Create a mock merge_fundamentals_from_cache that injects fund_data."""
    def _merge(symbols, target, values_key="values"):
        for sym in symbols:
            data = fund_data.get(sym)
            if data and sym in target:
                target[sym].setdefault(values_key, {}).update(data)
    return _merge


class TestGetBatchSparklines:
    @patch("app.services.compute.group.PriceRepository")
    @patch("app.services.compute.group.AssetRepository")
    async def test_returns_sparklines_for_group(self, mock_asset_repo_cls, mock_price_repo_cls, db):
        rows = [_make_asset_row(1, "AAPL"), _make_asset_row(2, "MSFT")]
        mock_asset_repo_cls.return_value.list_in_group_id_symbol_pairs = AsyncMock(return_value=rows)

        d1, d2 = date.today() - timedelta(days=2), date.today() - timedelta(days=1)
        prices = [
            _make_price(1, d1, 150.0), _make_price(1, d2, 152.0),
            _make_price(2, d1, 400.0), _make_price(2, d2, 405.0),
        ]
        mock_price_repo_cls.return_value.list_by_assets_since = AsyncMock(return_value=prices)

        result = await get_batch_sparklines(db, period="3mo", group_id=1)

        assert "AAPL" in result
        assert "MSFT" in result
        assert len(result["AAPL"]) == 2
        assert result["AAPL"][0]["close"] == 150.0

    @patch("app.services.compute.group.PriceRepository")
    @patch("app.services.compute.group.AssetRepository")
    @patch("app.services.compute.group.GroupRepository")
    async def test_uses_default_group_when_no_id(self, mock_group_repo_cls, mock_asset_repo_cls, mock_price_repo_cls, db):
        default_group = MagicMock()
        default_group.id = 1
        mock_group_repo_cls.return_value.get_default = AsyncMock(return_value=default_group)
        mock_asset_repo_cls.return_value.list_in_group_id_symbol_pairs = AsyncMock(return_value=[])

        result = await get_batch_sparklines(db, period="3mo", group_id=None)
        assert result == {}

    @patch("app.services.compute.group.PriceRepository")
    @patch("app.services.compute.group.AssetRepository")
    async def test_empty_assets_returns_empty(self, mock_asset_repo_cls, mock_price_repo_cls, db):
        mock_asset_repo_cls.return_value.list_in_group_id_symbol_pairs = AsyncMock(return_value=[])

        result = await get_batch_sparklines(db, period="3mo", group_id=1)
        assert result == {}


class TestComputeAndCacheIndicators:
    @patch("app.services.compute.group.merge_fundamentals_from_cache")
    @patch("app.services.compute.group.build_indicator_snapshot")
    @patch("app.services.compute.group.compute_indicators")
    @patch("app.services.compute.group.prices_to_df")
    @patch("app.services.compute.group.PriceRepository")
    @patch("app.services.compute.group.AssetRepository")
    async def test_computes_snapshots(
        self, mock_asset_repo_cls, mock_price_repo_cls, mock_prices_to_df,
        mock_compute_ind, mock_build_snap, mock_merge_fund, db,
    ):
        _indicator_cache._data.clear()

        rows = [_make_asset_row(1, "AAPL")]
        mock_asset_repo_cls.return_value.list_in_group_id_symbol_pairs = AsyncMock(return_value=rows)

        today = date.today()
        prices = [_make_price(1, today - timedelta(days=i), 150.0 + i) for i in range(30)]
        mock_price_repo_cls.return_value.list_by_assets_since = AsyncMock(return_value=prices)
        mock_price_repo_cls.return_value.get_latest_date = AsyncMock(return_value=today)

        mock_prices_to_df.return_value = MagicMock()
        mock_compute_ind.return_value = MagicMock()
        mock_build_snap.return_value = {"values": {"rsi": 55.0}}
        mock_merge_fund.side_effect = _mock_merge_fundamentals({"AAPL": {"forward_pe": 28.5}})

        result = await compute_and_cache_indicators(db, group_id=1)

        assert "AAPL" in result
        assert result["AAPL"]["values"]["rsi"] == 55.0
        assert result["AAPL"]["values"]["forward_pe"] == 28.5
        mock_merge_fund.assert_called_once()

        _indicator_cache._data.clear()

    @patch("app.services.compute.group.merge_fundamentals_from_cache")
    @patch("app.services.compute.group.PriceRepository")
    @patch("app.services.compute.group.AssetRepository")
    async def test_skips_assets_with_too_few_prices(
        self, mock_asset_repo_cls, mock_price_repo_cls, mock_merge_fund, db,
    ):
        _indicator_cache._data.clear()

        rows = [_make_asset_row(1, "NEW")]
        mock_asset_repo_cls.return_value.list_in_group_id_symbol_pairs = AsyncMock(return_value=rows)

        # Only 10 prices — less than 26 needed for MACD
        prices = [_make_price(1, date.today() - timedelta(days=i), 50.0) for i in range(10)]
        mock_price_repo_cls.return_value.list_by_assets_since = AsyncMock(return_value=prices)
        mock_price_repo_cls.return_value.get_latest_date = AsyncMock(return_value=date.today())

        result = await compute_and_cache_indicators(db, group_id=1)

        assert result["NEW"] == {"values": {}}

        _indicator_cache._data.clear()

    @patch("app.services.compute.group.PriceRepository")
    @patch("app.services.compute.group.AssetRepository")
    async def test_empty_assets_returns_empty(self, mock_asset_repo_cls, mock_price_repo_cls, db):
        mock_asset_repo_cls.return_value.list_in_group_id_symbol_pairs = AsyncMock(return_value=[])

        result = await compute_and_cache_indicators(db, group_id=1)
        assert result == {}

    @patch("app.services.compute.group.merge_fundamentals_from_cache")
    @patch("app.services.compute.group.build_indicator_snapshot")
    @patch("app.services.compute.group.compute_indicators")
    @patch("app.services.compute.group.prices_to_df")
    @patch("app.services.compute.group.PriceRepository")
    @patch("app.services.compute.group.AssetRepository")
    async def test_cache_hit_skips_computation(
        self, mock_asset_repo_cls, mock_price_repo_cls, mock_prices_to_df,
        mock_compute_ind, mock_build_snap, mock_merge_fund, db,
    ):
        _indicator_cache._data.clear()

        rows = [_make_asset_row(1, "AAPL")]
        mock_asset_repo_cls.return_value.list_in_group_id_symbol_pairs = AsyncMock(return_value=rows)

        today = date.today()
        prices = [_make_price(1, today - timedelta(days=i), 150.0 + i) for i in range(30)]
        mock_price_repo_cls.return_value.list_by_assets_since = AsyncMock(return_value=prices)
        mock_price_repo_cls.return_value.get_latest_date = AsyncMock(return_value=today)

        mock_prices_to_df.return_value = MagicMock()
        mock_compute_ind.return_value = MagicMock()
        mock_build_snap.return_value = {"values": {"rsi": 55.0}}

        # First call populates cache
        await compute_and_cache_indicators(db, group_id=1)
        call_count_1 = mock_compute_ind.call_count

        # Second call should use cache
        await compute_and_cache_indicators(db, group_id=1)
        assert mock_compute_ind.call_count == call_count_1  # No additional calls

        _indicator_cache._data.clear()

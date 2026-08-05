"""Tests for batch indicator computation and sparkline data (group.py)."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain import AssetRef
from app.services.compute.group import (
    _indicator_cache,
    compute_and_cache_indicators,
    compute_indicators_for_symbols,
    get_batch_sparklines,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


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
        refs = [AssetRef("AAPL", 1), AssetRef("MSFT", 2)]
        mock_asset_repo_cls.return_value.list_in_group_refs = AsyncMock(return_value=refs)

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
        mock_asset_repo_cls.return_value.list_in_group_refs = AsyncMock(return_value=[])

        result = await get_batch_sparklines(db, period="3mo", group_id=None)
        assert result == {}

    @patch("app.services.compute.group.PriceRepository")
    @patch("app.services.compute.group.AssetRepository")
    async def test_empty_assets_returns_empty(self, mock_asset_repo_cls, mock_price_repo_cls, db):
        mock_asset_repo_cls.return_value.list_in_group_refs = AsyncMock(return_value=[])

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

        refs = [AssetRef("AAPL", 1)]
        mock_asset_repo_cls.return_value.list_in_group_refs = AsyncMock(return_value=refs)

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

        refs = [AssetRef("NEW", 1)]
        mock_asset_repo_cls.return_value.list_in_group_refs = AsyncMock(return_value=refs)

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
        mock_asset_repo_cls.return_value.list_in_group_refs = AsyncMock(return_value=[])

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

        refs = [AssetRef("AAPL", 1)]
        mock_asset_repo_cls.return_value.list_in_group_refs = AsyncMock(return_value=refs)

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


class TestComputeIndicatorsForSymbols:
    @patch("app.services.compute.group.merge_fundamentals_from_cache")
    @patch("app.services.compute.group.build_indicator_snapshot")
    @patch("app.services.compute.group.compute_indicators")
    @patch("app.services.compute.group.prices_to_df")
    @patch("app.services.compute.group.PriceRepository")
    @patch("app.services.compute.group.AssetRepository")
    async def test_computes_snapshots_for_symbols(
        self, mock_asset_repo_cls, mock_price_repo_cls, mock_prices_to_df,
        mock_compute_ind, mock_build_snap, mock_merge_fund, db,
    ):
        _indicator_cache._data.clear()

        # Only the tracked symbol resolves to a ref; "GHOST" is dropped by the repo.
        refs = [AssetRef("AAPL", 1)]
        mock_asset_repo_cls.return_value.list_refs_by_symbols = AsyncMock(return_value=refs)

        today = date.today()
        prices = [_make_price(1, today - timedelta(days=i), 150.0 + i) for i in range(30)]
        mock_price_repo_cls.return_value.list_by_assets_since = AsyncMock(return_value=prices)
        mock_price_repo_cls.return_value.get_latest_date = AsyncMock(return_value=today)

        mock_prices_to_df.return_value = MagicMock()
        mock_compute_ind.return_value = MagicMock()
        mock_build_snap.return_value = {"values": {"rsi": 55.0}}
        mock_merge_fund.side_effect = _mock_merge_fundamentals({})

        result = await compute_indicators_for_symbols(db, ["AAPL", "GHOST"])

        assert set(result) == {"AAPL"}
        assert result["AAPL"]["values"]["rsi"] == 55.0
        mock_asset_repo_cls.return_value.list_refs_by_symbols.assert_awaited_once_with(
            ["AAPL", "GHOST"]
        )

        _indicator_cache._data.clear()

    @patch("app.services.compute.group.AssetRepository")
    async def test_empty_symbols_short_circuits(self, mock_asset_repo_cls, db):
        result = await compute_indicators_for_symbols(db, [])

        assert result == {}
        # No DB work for an empty symbol set.
        mock_asset_repo_cls.return_value.list_refs_by_symbols.assert_not_called()

    @patch("app.services.compute.group.merge_fundamentals_from_cache")
    @patch("app.services.compute.group.build_indicator_snapshot")
    @patch("app.services.compute.group.compute_indicators")
    @patch("app.services.compute.group.prices_to_df")
    @patch("app.services.compute.group.PriceRepository")
    @patch("app.services.compute.group.AssetRepository")
    async def test_cache_shared_across_scopes(
        self, mock_asset_repo_cls, mock_price_repo_cls, mock_prices_to_df,
        mock_compute_ind, mock_build_snap, mock_merge_fund, db,
    ):
        """Regression for #529: the cache key is scope-independent, so a group
        page (group_id) and the symbol-addressed endpoint (None) share the entry
        when the symbol set + latest date match — no redundant recompute."""
        _indicator_cache._data.clear()

        ref = AssetRef("AAPL", 1)
        # Both entry points resolve the same symbol set to the same ref.
        mock_asset_repo_cls.return_value.list_in_group_refs = AsyncMock(return_value=[ref])
        mock_asset_repo_cls.return_value.list_refs_by_symbols = AsyncMock(return_value=[ref])

        today = date.today()
        prices = [_make_price(1, today - timedelta(days=i), 150.0 + i) for i in range(30)]
        mock_price_repo_cls.return_value.list_by_assets_since = AsyncMock(return_value=prices)
        mock_price_repo_cls.return_value.get_latest_date = AsyncMock(return_value=today)

        mock_prices_to_df.return_value = MagicMock()
        mock_compute_ind.return_value = MagicMock()
        mock_build_snap.return_value = {"values": {"rsi": 55.0}}
        mock_merge_fund.side_effect = _mock_merge_fundamentals({})

        # Group call populates the cache.
        await compute_and_cache_indicators(db, group_id=1)
        calls_after_group = mock_compute_ind.call_count
        assert calls_after_group > 0

        # Symbol-addressed call for the same symbol set must hit that entry, not recompute.
        await compute_indicators_for_symbols(db, ["AAPL"])
        assert mock_compute_ind.call_count == calls_after_group

        _indicator_cache._data.clear()

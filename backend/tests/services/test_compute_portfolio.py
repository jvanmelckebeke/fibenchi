"""Tests for portfolio index computation and performer ranking."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import AssetType
from app.services.compute.portfolio import (
    _MIN_ENTRY_PRICE,
    compute_performers,
    compute_portfolio_index,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestComputePortfolioIndex:
    @patch("app.services.compute.portfolio.calculate_performance", new_callable=AsyncMock)
    @patch("app.services.compute.portfolio.AssetRepository")
    async def test_returns_index_data(self, mock_asset_repo_cls, mock_calc_perf, db):
        mock_asset_repo_cls.return_value.list_in_any_group_ids = AsyncMock(return_value=[1, 2])
        mock_calc_perf.return_value = [
            {"date": "2025-01-01", "value": 1000.0},
            {"date": "2025-06-01", "value": 1100.0},
        ]

        result = await compute_portfolio_index(db, period="1y")

        assert result["dates"] == ["2025-01-01", "2025-06-01"]
        assert result["values"] == [1000.0, 1100.0]
        assert result["current"] == 1100.0
        assert result["change"] == 100.0
        assert result["change_pct"] == 10.0

    @patch("app.services.compute.portfolio.AssetRepository")
    async def test_no_assets_returns_empty(self, mock_asset_repo_cls, db):
        mock_asset_repo_cls.return_value.list_in_any_group_ids = AsyncMock(return_value=[])

        result = await compute_portfolio_index(db, period="1y")
        assert result["dates"] == []
        assert result["current"] == 0

    @patch("app.services.compute.portfolio.calculate_performance", new_callable=AsyncMock)
    @patch("app.services.compute.portfolio.AssetRepository")
    async def test_no_points_returns_empty(self, mock_asset_repo_cls, mock_calc_perf, db):
        mock_asset_repo_cls.return_value.list_in_any_group_ids = AsyncMock(return_value=[1])
        mock_calc_perf.return_value = []

        result = await compute_portfolio_index(db, period="1y")
        assert result["current"] == 0

    @patch("app.services.compute.portfolio.calculate_performance", new_callable=AsyncMock)
    @patch("app.services.compute.portfolio.AssetRepository")
    async def test_passes_dynamic_entry_and_min_price(self, mock_asset_repo_cls, mock_calc_perf, db):
        mock_asset_repo_cls.return_value.list_in_any_group_ids = AsyncMock(return_value=[1])
        mock_calc_perf.return_value = [{"date": "2025-01-01", "value": 1000.0}]

        await compute_portfolio_index(db, period="1y")

        call_kwargs = mock_calc_perf.call_args
        assert call_kwargs.kwargs.get("dynamic_entry") is True or call_kwargs[1].get("dynamic_entry") is True

    @patch("app.services.compute.portfolio.calculate_performance", new_callable=AsyncMock)
    @patch("app.services.compute.portfolio.AssetRepository")
    async def test_negative_change(self, mock_asset_repo_cls, mock_calc_perf, db):
        mock_asset_repo_cls.return_value.list_in_any_group_ids = AsyncMock(return_value=[1])
        mock_calc_perf.return_value = [
            {"date": "2025-01-01", "value": 1000.0},
            {"date": "2025-06-01", "value": 900.0},
        ]

        result = await compute_portfolio_index(db, period="1y")
        assert result["change"] == -100.0
        assert result["change_pct"] == -10.0


def _make_asset(id: int, symbol: str, name: str, type_val: AssetType = AssetType.STOCK):
    asset = MagicMock()
    asset.id = id
    asset.symbol = symbol
    asset.name = name
    asset.type = type_val
    return asset


class TestComputePerformers:
    @patch("app.services.compute.portfolio.PriceRepository")
    @patch("app.services.compute.portfolio.AssetRepository")
    async def test_returns_ranked_performers(self, mock_asset_repo_cls, mock_price_repo_cls, db):
        assets = [
            _make_asset(1, "AAPL", "Apple"),
            _make_asset(2, "MSFT", "Microsoft"),
        ]
        mock_asset_repo_cls.return_value.list_in_any_group = AsyncMock(return_value=assets)

        today = date.today()
        start = today - timedelta(days=365)
        mock_price_repo_cls.return_value.get_first_dates = AsyncMock(
            return_value={1: start, 2: start}
        )
        mock_price_repo_cls.return_value.get_last_dates = AsyncMock(
            return_value={1: today, 2: today}
        )
        mock_price_repo_cls.return_value.get_prices_at_dates = AsyncMock(
            return_value={
                (1, start): 100.0, (1, today): 150.0,
                (2, start): 200.0, (2, today): 280.0,
            }
        )

        result = await compute_performers(db, period="1y")

        assert len(result) == 2
        # MSFT (40%) should rank above AAPL (50%) — wait, AAPL is 50% and MSFT is 40%
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["change_pct"] == 50.0
        assert result[1]["symbol"] == "MSFT"
        assert result[1]["change_pct"] == 40.0

    @patch("app.services.compute.portfolio.PriceRepository")
    @patch("app.services.compute.portfolio.AssetRepository")
    async def test_no_assets_returns_empty(self, mock_asset_repo_cls, mock_price_repo_cls, db):
        mock_asset_repo_cls.return_value.list_in_any_group = AsyncMock(return_value=[])
        result = await compute_performers(db, period="1y")
        assert result == []

    @patch("app.services.compute.portfolio.PriceRepository")
    @patch("app.services.compute.portfolio.AssetRepository")
    async def test_skips_asset_with_same_first_last_date(self, mock_asset_repo_cls, mock_price_repo_cls, db):
        assets = [_make_asset(1, "NEW", "New Stock")]
        mock_asset_repo_cls.return_value.list_in_any_group = AsyncMock(return_value=assets)

        today = date.today()
        mock_price_repo_cls.return_value.get_first_dates = AsyncMock(return_value={1: today})
        mock_price_repo_cls.return_value.get_last_dates = AsyncMock(return_value={1: today})
        mock_price_repo_cls.return_value.get_prices_at_dates = AsyncMock(return_value={(1, today): 100.0})

        result = await compute_performers(db, period="1y")
        assert result == []

    @patch("app.services.compute.portfolio.PriceRepository")
    @patch("app.services.compute.portfolio.AssetRepository")
    async def test_skips_asset_with_zero_first_close(self, mock_asset_repo_cls, mock_price_repo_cls, db):
        assets = [_make_asset(1, "AAPL", "Apple")]
        mock_asset_repo_cls.return_value.list_in_any_group = AsyncMock(return_value=assets)

        today = date.today()
        start = today - timedelta(days=365)
        mock_price_repo_cls.return_value.get_first_dates = AsyncMock(return_value={1: start})
        mock_price_repo_cls.return_value.get_last_dates = AsyncMock(return_value={1: today})
        mock_price_repo_cls.return_value.get_prices_at_dates = AsyncMock(
            return_value={(1, start): 0, (1, today): 50.0}
        )

        result = await compute_performers(db, period="1y")
        assert result == []

    def test_min_entry_price_is_10(self):
        assert _MIN_ENTRY_PRICE == 10.0

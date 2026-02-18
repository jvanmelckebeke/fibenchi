"""Unit tests for price_service — tests caching, ephemeral fetch, warmup logic."""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

from app.models import Asset, AssetType, PriceHistory
from app.services.price_service import (
    _display_start,
    _fetch_ephemeral,
    get_detail,
    get_indicators,
    get_prices,
    refresh_prices,
)




def _make_asset(**overrides) -> Asset:
    defaults = dict(id=1, symbol="AAPL", name="Apple", type=AssetType.STOCK, currency="USD")
    defaults.update(overrides)
    return Asset(**defaults)


def _make_price_history(asset_id: int = 1, n_days: int = 100, base_price: float = 100.0) -> list[PriceHistory]:
    today = date.today()
    prices = []
    for i in range(n_days):
        d = today - timedelta(days=n_days - 1 - i)
        if d.weekday() >= 5:
            continue
        price = base_price + i * 0.1
        prices.append(PriceHistory(
            id=i + 1, asset_id=asset_id, date=d,
            open=round(price - 0.5, 4), high=round(price + 1.0, 4),
            low=round(price - 1.0, 4), close=round(price, 4),
            volume=1_000_000,
        ))
    return prices


def test_display_start_calculates_correct_date():
    result = _display_start("3mo")
    expected = date.today() - timedelta(days=90)
    assert result == expected


def test_display_start_unknown_period_defaults_90():
    result = _display_start("unknown")
    expected = date.today() - timedelta(days=90)
    assert result == expected


async def test_fetch_ephemeral_raises_404_on_empty():
    empty_df = pd.DataFrame()
    with patch("app.services.price_service.fetch_history", new_callable=AsyncMock, return_value=empty_df):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await _fetch_ephemeral("XXXX", "3mo")
        assert exc_info.value.status_code == 404


async def test_fetch_ephemeral_raises_404_on_error():
    with patch("app.services.price_service.fetch_history", new_callable=AsyncMock, side_effect=ValueError("No data")):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await _fetch_ephemeral("XXXX", "3mo")
        assert exc_info.value.status_code == 404


@patch("app.services.price_service.PriceRepository")
@patch("app.services.price_service.sync_asset_prices", new_callable=AsyncMock)
async def test_ensure_prices_syncs_when_empty(mock_sync, MockPriceRepo):
    """When no prices exist in DB, _ensure_prices triggers a sync."""
    db = AsyncMock()
    asset = _make_asset()
    mock_repo = MockPriceRepo.return_value
    # First call returns empty, second (after sync) returns prices
    prices = _make_price_history()
    mock_repo.list_by_asset = AsyncMock(side_effect=[[], prices])
    mock_sync.return_value = len(prices)

    from app.services.price_service import _ensure_prices
    result = await _ensure_prices(db, asset, "3mo")

    mock_sync.assert_awaited_once()
    assert len(result) > 0


async def test_get_prices_filters_by_period():
    """get_prices with a DB asset delegates to _ensure_prices and filters by start date."""
    db = AsyncMock()
    asset = _make_asset()
    prices = _make_price_history(n_days=500)

    with patch("app.services.price_service._ensure_prices", new_callable=AsyncMock, return_value=prices):
        result = await get_prices(db, asset, "AAPL", "3mo")

    cutoff = _display_start("3mo")
    assert all(p.date >= cutoff for p in result)


@patch("app.services.price_service._indicator_cache")
@patch("app.services.price_service.PriceRepository")
async def test_get_indicators_uses_cache(MockPriceRepo, mock_cache):
    """Cached indicators are returned without recomputation."""
    db = AsyncMock()
    asset = _make_asset()
    prices = _make_price_history(n_days=200)
    cached_rows = [{"date": date.today(), "close": 100.0, "rsi": 55.0}]

    mock_cache.get_value.return_value = cached_rows

    with patch("app.services.price_service._ensure_prices", new_callable=AsyncMock, return_value=prices):
        result = await get_indicators(db, asset, "AAPL", "3mo")

    assert result == cached_rows


@patch("app.services.price_service.sync_asset_prices", new_callable=AsyncMock)
async def test_refresh_delegates_to_sync(mock_sync):
    db = AsyncMock()
    asset = _make_asset()
    mock_sync.return_value = 42

    result = await refresh_prices(db, asset, "3mo")

    mock_sync.assert_awaited_once_with(db, asset, period="3mo")
    assert result == {"symbol": "AAPL", "synced": 42}

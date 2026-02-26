"""Unit tests for price_service — tests caching, ephemeral fetch, warmup logic."""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

from app.models import Asset, AssetType, PriceHistory
from app.services.price_service import (
    _backfill_already_attempted,
    _display_start,
    _earliest_date_cache,
    _fetch_ephemeral,
    get_detail,
    get_indicators,
    get_prices,
    refresh_prices,
)

from tests.helpers import make_model_asset as _make_asset

pytestmark = pytest.mark.asyncio(loop_scope="function")


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


def _mock_provider(**overrides):
    """Create a mock PriceProvider with async method stubs."""
    provider = MagicMock()
    provider.fetch_history = AsyncMock(
        return_value=overrides.get("fetch_history", pd.DataFrame())
    )
    return provider


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
    mock_prov = _mock_provider(fetch_history=empty_df)
    with patch("app.services.price_service.get_price_provider", return_value=mock_prov):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await _fetch_ephemeral("XXXX", "3mo")
        assert exc_info.value.status_code == 404


async def test_fetch_ephemeral_raises_404_on_error():
    mock_prov = MagicMock()
    mock_prov.fetch_history = AsyncMock(side_effect=ValueError("No data"))
    with patch("app.services.price_service.get_price_provider", return_value=mock_prov):
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


# ---------------------------------------------------------------------------
# Tests for earliest-date cache (skip redundant Yahoo fetches)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_earliest_cache():
    """Ensure the earliest-date cache is empty before each test."""
    _earliest_date_cache.clear()
    yield
    _earliest_date_cache.clear()


def test_backfill_already_attempted_no_cache():
    """Without any cache entry, _backfill_already_attempted returns False."""
    assert _backfill_already_attempted(1, date(2021, 1, 1)) is False


def test_backfill_already_attempted_with_cache():
    """With a cached earliest date, returns True when requested start is before it."""
    _earliest_date_cache.set_value(1, date(2022, 9, 30))
    # Requesting data from 2021 — earlier than the cached earliest 2022-09-30
    assert _backfill_already_attempted(1, date(2021, 1, 1)) is True
    # Requesting data from exactly the cached date
    assert _backfill_already_attempted(1, date(2022, 9, 30)) is True


def test_backfill_already_attempted_cache_does_not_block_newer_requests():
    """Cache does not interfere when requested start is after the cached earliest."""
    _earliest_date_cache.set_value(1, date(2022, 9, 30))
    # Requesting data from 2023 — after the cached earliest, so this is a normal
    # gap (maybe the daily cron missed some data), not a "stock didn't exist" gap.
    assert _backfill_already_attempted(1, date(2023, 1, 1)) is False


@patch("app.services.price_service.PriceRepository")
@patch("app.services.price_service.sync_asset_prices_range", new_callable=AsyncMock)
async def test_ensure_prices_caches_earliest_after_noop_backfill(mock_sync_range, MockPriceRepo):
    """After a backfill attempt that doesn't move the earliest date, the cache is populated."""
    db = AsyncMock()
    asset = _make_asset(id=42)
    # Simulate stock that IPO'd ~200 days ago — prices start at day -200
    prices = _make_price_history(asset_id=42, n_days=200)
    earliest = prices[0].date

    mock_repo = MockPriceRepo.return_value
    # list_by_asset called twice: once initially, once after sync
    mock_repo.list_by_asset = AsyncMock(side_effect=[prices, prices])
    mock_sync_range.return_value = 0  # sync returned nothing new

    from app.services.price_service import _ensure_prices
    await _ensure_prices(db, asset, "5y")  # 5y goes back ~1825 days

    # sync_asset_prices_range was called (first attempt)
    mock_sync_range.assert_awaited_once()
    # earliest date is now cached
    cached = _earliest_date_cache.get_value(42)
    assert cached == earliest


@patch("app.services.price_service.PriceRepository")
@patch("app.services.price_service.sync_asset_prices_range", new_callable=AsyncMock)
async def test_ensure_prices_skips_fetch_on_second_request(mock_sync_range, MockPriceRepo):
    """Second request for the same long period skips the Yahoo fetch entirely."""
    db = AsyncMock()
    asset = _make_asset(id=42)
    prices = _make_price_history(asset_id=42, n_days=200)

    mock_repo = MockPriceRepo.return_value

    # First call: sync is attempted, earliest doesn't move
    mock_repo.list_by_asset = AsyncMock(side_effect=[prices, prices])
    mock_sync_range.return_value = 0

    from app.services.price_service import _ensure_prices
    await _ensure_prices(db, asset, "5y")
    assert mock_sync_range.await_count == 1

    # Second call: sync should be skipped because cache knows there's no more data
    mock_repo.list_by_asset = AsyncMock(return_value=prices)
    await _ensure_prices(db, asset, "5y")
    # Still only 1 call — the second request did NOT trigger sync
    assert mock_sync_range.await_count == 1


@patch("app.services.price_service.PriceRepository")
@patch("app.services.price_service.sync_asset_prices_range", new_callable=AsyncMock)
async def test_ensure_prices_does_not_cache_when_backfill_succeeds(mock_sync_range, MockPriceRepo):
    """When backfill actually moves the earliest date, don't cache (more data may exist)."""
    db = AsyncMock()
    asset = _make_asset(id=42)
    # Initial prices start 200 days ago
    prices_before = _make_price_history(asset_id=42, n_days=200)
    # After sync, prices now start 400 days ago (backfill succeeded)
    prices_after = _make_price_history(asset_id=42, n_days=400)

    mock_repo = MockPriceRepo.return_value
    mock_repo.list_by_asset = AsyncMock(side_effect=[prices_before, prices_after])
    mock_sync_range.return_value = 200

    from app.services.price_service import _ensure_prices
    await _ensure_prices(db, asset, "5y")

    # Sync was called
    mock_sync_range.assert_awaited_once()
    # Cache should NOT be populated — more data might exist even further back
    cached = _earliest_date_cache.get_value(42)
    assert cached is None

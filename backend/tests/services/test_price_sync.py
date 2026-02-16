"""Tests for the price_sync service (sync orchestration and upsert logic)."""

import pytest
from datetime import date
from unittest.mock import patch, AsyncMock

import pandas as pd

from app.models import Asset, AssetType
from app.services.price_sync import (
    sync_asset_prices,
    sync_asset_prices_range,
    sync_all_prices,
    _upsert_prices,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


def _make_df(n=10, base_price=100.0):
    """Create a minimal OHLCV DataFrame."""
    dates = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({
        "open": [base_price] * n,
        "high": [base_price + 1] * n,
        "low": [base_price - 1] * n,
        "close": [base_price + 0.5] * n,
        "volume": [1_000_000] * n,
    }, index=dates)


# --- sync_asset_prices ---

async def test_sync_calls_fetch_with_period(db):
    """sync_asset_prices passes the period to fetch_history."""
    asset = Asset(symbol="TEST", name="Test", type=AssetType.STOCK, currency="USD")
    db.add(asset)
    await db.flush()

    mock_df = _make_df()
    with patch("app.services.price_sync.fetch_history", return_value=mock_df) as mock_fetch, \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=10):
        count = await sync_asset_prices(db, asset, period="6mo")

    mock_fetch.assert_called_once_with("TEST", period="6mo")
    assert count == 10


async def test_sync_returns_upsert_count(db):
    """Return value matches what _upsert_prices returns."""
    asset = Asset(symbol="X", name="X", type=AssetType.STOCK, currency="USD")
    db.add(asset)
    await db.flush()

    with patch("app.services.price_sync.fetch_history", return_value=_make_df()), \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=7):
        assert await sync_asset_prices(db, asset) == 7


# --- sync_asset_prices_range ---

async def test_sync_range_passes_dates(db):
    """sync_asset_prices_range passes start/end to fetch_history."""
    asset = Asset(symbol="RNG", name="Range", type=AssetType.STOCK, currency="USD")
    db.add(asset)
    await db.flush()

    start, end = date(2025, 1, 1), date(2025, 6, 30)
    with patch("app.services.price_sync.fetch_history", return_value=_make_df()) as mock_fetch, \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=5):
        count = await sync_asset_prices_range(db, asset, start, end)

    mock_fetch.assert_called_once_with("RNG", start=start, end=end)
    assert count == 5


# --- _upsert_prices ---

async def test_upsert_empty_dataframe(db):
    """Empty DataFrame returns 0 without touching the DB."""
    count = await _upsert_prices(db, 999, pd.DataFrame())
    assert count == 0


# --- sync_all_prices ---

async def test_sync_all_fetches_batch(db):
    """sync_all_prices calls batch_fetch_history for all assets in DB."""
    a1 = Asset(symbol="AAPL", name="Apple", type=AssetType.STOCK, currency="USD")
    a2 = Asset(symbol="MSFT", name="Microsoft", type=AssetType.STOCK, currency="USD")
    db.add_all([a1, a2])
    await db.commit()

    mock_data = {"AAPL": _make_df(), "MSFT": _make_df()}
    with patch("app.services.price_sync.batch_fetch_history", return_value=mock_data) as mock_fetch, \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=10):
        counts = await sync_all_prices(db, period="1y")

    # Verify batch_fetch_history was called with both symbols
    call_args = mock_fetch.call_args
    assert set(call_args[0][0]) == {"AAPL", "MSFT"}
    assert call_args[1]["period"] == "1y"
    assert counts == {"AAPL": 10, "MSFT": 10}


async def test_sync_all_empty_db(db):
    """No assets in DB returns empty dict."""
    counts = await sync_all_prices(db)
    assert counts == {}


async def test_sync_all_skips_unknown_symbols(db):
    """Symbols returned by Yahoo but not in DB are ignored."""
    a1 = Asset(symbol="AAPL", name="Apple", type=AssetType.STOCK, currency="USD")
    db.add(a1)
    await db.commit()

    # Yahoo returns data for AAPL and an unknown EXTRA symbol
    mock_data = {"AAPL": _make_df(), "EXTRA": _make_df()}
    with patch("app.services.price_sync.batch_fetch_history", return_value=mock_data), \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=10):
        counts = await sync_all_prices(db, period="1y")

    assert "AAPL" in counts
    assert "EXTRA" not in counts

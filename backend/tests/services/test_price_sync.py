"""Tests for the price_sync service (sync orchestration and upsert logic)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.models import Asset, AssetType
from app.services.price_sync import (
    _upsert_prices,
    drop_unsettled_last_bar,
    sync_all_prices,
    sync_asset_prices,
    sync_asset_prices_range,
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


def _df_from_closes(closes):
    """OHLCV DataFrame with the given trailing close sequence (bdate index)."""
    n = len(closes)
    dates = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1_000_000] * n,
    }, index=dates)


def _mock_provider(**overrides):
    """Create a mock PriceProvider with async method stubs."""
    provider = MagicMock()
    provider.fetch_history = AsyncMock(return_value=overrides.get("fetch_history", _make_df()))
    provider.batch_fetch_history = AsyncMock(return_value=overrides.get("batch_fetch_history", {}))
    provider.batch_fetch_quotes = AsyncMock(return_value=overrides.get("batch_fetch_quotes", []))
    return provider


# --- sync_asset_prices ---

async def test_sync_calls_fetch_with_period(db):
    """sync_asset_prices passes the period to fetch_history."""
    asset = Asset(symbol="TEST", name="Test", type=AssetType.STOCK, currency="USD")
    db.add(asset)
    await db.flush()

    mock_prov = _mock_provider()
    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=10):
        count = await sync_asset_prices(db, asset, period="6mo")

    mock_prov.fetch_history.assert_awaited_once_with("TEST", period="6mo")
    assert count == 10


async def test_sync_returns_upsert_count(db):
    """Return value matches what _upsert_prices returns."""
    asset = Asset(symbol="X", name="X", type=AssetType.STOCK, currency="USD")
    db.add(asset)
    await db.flush()

    mock_prov = _mock_provider()
    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=7):
        assert await sync_asset_prices(db, asset) == 7


# --- sync_asset_prices_range ---

async def test_sync_range_passes_dates(db):
    """sync_asset_prices_range passes start/end to fetch_history."""
    asset = Asset(symbol="RNG", name="Range", type=AssetType.STOCK, currency="USD")
    db.add(asset)
    await db.flush()

    start, end = date(2025, 1, 1), date(2025, 6, 30)
    mock_prov = _mock_provider()
    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=5):
        count = await sync_asset_prices_range(db, asset, start, end)

    mock_prov.fetch_history.assert_awaited_once_with("RNG", start=start, end=end)
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
    mock_prov = _mock_provider(batch_fetch_history=mock_data)
    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=10):
        counts = await sync_all_prices(db, period="1y")

    # Verify batch_fetch_history was called with both symbols
    call_args = mock_prov.batch_fetch_history.call_args
    assert set(call_args[0][0]) == {"AAPL", "MSFT"}
    assert call_args[1]["period"] == "1y"
    assert counts == {"AAPL": 10, "MSFT": 10}


async def test_sync_all_empty_db(db):
    """No assets in DB returns empty dict."""
    counts = await sync_all_prices(db)
    assert counts == {}


async def test_sync_all_skips_unknown_symbols(db):
    """Symbols returned by the provider but not in DB are ignored."""
    a1 = Asset(symbol="AAPL", name="Apple", type=AssetType.STOCK, currency="USD")
    db.add(a1)
    await db.commit()

    # Provider returns data for AAPL and an unknown EXTRA symbol
    mock_data = {"AAPL": _make_df(), "EXTRA": _make_df()}
    mock_prov = _mock_provider(batch_fetch_history=mock_data)
    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=10):
        counts = await sync_all_prices(db, period="1y")

    assert "AAPL" in counts
    assert "EXTRA" not in counts


# --- drop_unsettled_last_bar (settlement reconciliation) ---
#
# The last stored bar must reconcile with the live quote or the frontend blanks
# σ-Move. Each case names a real ticker observed on the watchlist (group 5).

@pytest.mark.parametrize("name,closes,price,prev,state,expect_drop", [
    # In-progress US session (REGULAR): partial bar, drop even though it matched
    # the live price at capture — it drifts as the session continues (IBM's case).
    ("IBM open-partial", [305.0, 290.23, 224.14], 220.84, 290.23, "REGULAR", True),
    # Open session whose partial still matches the live price now: still dropped,
    # because keeping it would blank σ-Move once the price moves on (MNST's case).
    ("MNST open", [96.5, 97.07, 97.44], 97.565, 97.07, "REGULAR", True),
    # Closed EU session, Yahoo daily bar not yet settled to the official close.
    ("PRY.MI unsettled", [130.0, 133.35, 137.0], 137.85, 133.35, "POSTPOST", True),
    # Closed session, within 0.5% of the settled close — keep (shows stored vnr).
    ("MT.AS within-tol", [57.5, 58.04, 59.0], 58.72, 58.04, "POSTPOST", False),
    # Closed, exact settled close — keep (Asian bar published overnight: f69ff59).
    ("001440.KS settled", [28500.0, 28300.0, 28000.0], 28000.0, 28300.0, "PREPRE", False),
    # Fully closed session, last bar equals current price — keep.
    ("completed bar", [90.0, 95.0, 100.0], 100.0, 95.0, "CLOSED", False),
])
async def test_drop_unsettled_cases(name, closes, price, prev, state, expect_drop):
    df = _df_from_closes(closes)
    out = drop_unsettled_last_bar(df, price, prev, state)
    if expect_drop:
        assert len(out) == len(df) - 1, name
        assert float(out.iloc[-1]["close"]) == closes[-2], name
    else:
        assert len(out) == len(df), name


async def test_drop_unsettled_no_today_bar_kept():
    """Market open but no current-session bar yet (halt): completed bar is kept."""
    # Last bar (100.0) is yesterday's completed close == quote previous_close;
    # its predecessor (98.0) does NOT match previous_close, so it's not treated
    # as an in-progress session even though today's live price (101.0) differs.
    df = _df_from_closes([95.0, 98.0, 100.0])
    out = drop_unsettled_last_bar(df, price=101.0, previous_close=100.0, market_state="REGULAR")
    assert len(out) == len(df)


async def test_drop_unsettled_missing_quote_kept():
    """No quote anchors (fetch failed) → store every bar (prior behaviour)."""
    df = _df_from_closes([100.0, 105.0, 130.0])
    assert len(drop_unsettled_last_bar(df, None, None, "REGULAR")) == len(df)
    assert len(drop_unsettled_last_bar(df, 130.0, None, "REGULAR")) == len(df)


async def test_drop_unsettled_short_frame_kept():
    """A single-row frame has no predecessor to reconcile — unchanged."""
    df = _df_from_closes([100.0])
    assert len(drop_unsettled_last_bar(df, 120.0, 100.0, "REGULAR")) == 1


async def test_sync_all_drops_unsettled_bar(db):
    """sync_all_prices strips the partial current-session bar before upsert."""
    a1 = Asset(symbol="IBM", name="IBM", type=AssetType.STOCK, currency="USD")
    db.add(a1)
    await db.commit()

    # 3 bars; last (224.14) is today's partial, predecessor (290.23) == prev close.
    mock_data = {"IBM": _df_from_closes([305.0, 290.23, 224.14])}
    quotes = [{"symbol": "IBM", "price": 220.84, "previous_close": 290.23,
               "market_state": "REGULAR"}]
    mock_prov = _mock_provider(batch_fetch_history=mock_data, batch_fetch_quotes=quotes)

    captured = {}

    async def _capture(*args):
        df = args[-1]
        captured["len"] = len(df)
        captured["last_close"] = float(df.iloc[-1]["close"])
        return len(df)

    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", side_effect=_capture):
        await sync_all_prices(db, period="1y")

    assert captured["len"] == 2  # 3 bars minus the dropped partial
    assert captured["last_close"] == 290.23  # last completed close remains


async def test_sync_all_keeps_settled_bar(db):
    """A closed, settled current-session bar (matches live close) is preserved."""
    a1 = Asset(symbol="MT.AS", name="ArcelorMittal", type=AssetType.STOCK, currency="EUR")
    db.add(a1)
    await db.commit()

    # Market closed (POSTPOST), last bar within tolerance of the settled close.
    mock_data = {"MT.AS": _df_from_closes([57.5, 58.04, 59.0])}
    quotes = [{"symbol": "MT.AS", "price": 58.72, "previous_close": 58.04,
               "market_state": "POSTPOST"}]
    mock_prov = _mock_provider(batch_fetch_history=mock_data, batch_fetch_quotes=quotes)

    captured = {}

    async def _capture(*args):
        captured["len"] = len(args[-1])
        return len(args[-1])

    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", side_effect=_capture):
        await sync_all_prices(db, period="1y")

    assert captured["len"] == 3  # nothing dropped

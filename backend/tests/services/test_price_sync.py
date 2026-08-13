"""Tests for the price_sync service (sync orchestration and upsert logic)."""

import logging
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.domain import AssetRef
from app.models import Asset, AssetType, PriceHistory
from app.repositories.price_repo import PriceRepository
from app.schemas.quote import Quote
from app.services.price_sync import (
    _NO_ANCHOR,
    _drop_and_persist,
    _drop_unanchored_trailing_bar,
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
        count = await sync_asset_prices(db, AssetRef.of(asset), period="6mo")

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
        count = await sync_asset_prices_range(db, AssetRef.of(asset), start, end)

    mock_prov.fetch_history.assert_awaited_once_with("RNG", start=start, end=end)
    assert count == 5


async def test_sync_range_past_skips_quote_roundtrip(db):
    """A purely historical range contains only settled bars — no anchor fetch."""
    asset = Asset(symbol="RNG", name="Range", type=AssetType.STOCK, currency="USD")
    db.add(asset)
    await db.flush()

    mock_prov = _mock_provider()
    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=3):
        await sync_asset_prices_range(db, AssetRef.of(asset), date(2025, 1, 1), date(2025, 6, 30))

    mock_prov.batch_fetch_quotes.assert_not_awaited()


async def test_sync_range_to_today_drops_unsettled_bar(db):
    """A range reaching today goes through the same drop guard as period syncs.

    Regression for the σ-Move blanking incident: a 1y detail-view backfill
    during EU market hours stored the live partial bar raw, which then drifted
    from the quote and blanked σ-Move for every affected symbol.
    """
    asset = Asset(symbol="MT.AS", name="ArcelorMittal", type=AssetType.STOCK, currency="EUR")
    db.add(asset)
    await db.flush()

    # Last close is today's live partial; its predecessor equals previous_close.
    df = _df_from_closes([60.0, 64.44, 63.10])
    quotes = [Quote(**{"symbol": "MT.AS", "price": 64.28, "previous_close": 64.44,
               "market_state": "REGULAR"})]
    mock_prov = _mock_provider(fetch_history=df, batch_fetch_quotes=quotes)

    captured = {}

    async def _capture(*args):
        captured["len"] = len(args[2])
        return len(args[2])

    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", side_effect=_capture):
        await sync_asset_prices_range(db, AssetRef.of(asset), date(2026, 1, 1), date.today())

    assert captured["len"] == 2  # partial dropped
    mock_prov.batch_fetch_quotes.assert_awaited_once()


async def test_sync_range_to_today_without_quote_stores_settled_bars(db):
    """Anchor unavailable → settled (historical) bars still store in full.

    The anchorless guard (#586) only withholds a trailing bar dated on the
    current session; this frame ends in Jan 2025, so nothing is withheld.
    """
    asset = Asset(symbol="MT.AS", name="ArcelorMittal", type=AssetType.STOCK, currency="EUR")
    db.add(asset)
    await db.flush()

    df = _df_from_closes([60.0, 64.44, 63.10])
    mock_prov = _mock_provider(fetch_history=df, batch_fetch_quotes=[])

    captured = {}

    async def _capture(*args):
        captured["len"] = len(args[2])
        return len(args[2])

    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", side_effect=_capture):
        await sync_asset_prices_range(db, AssetRef.of(asset), date(2026, 1, 1), date.today())

    assert captured["len"] == 3


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


async def test_sync_all_retries_symbols_missing_from_batch(db, caplog):
    """Symbols Yahoo silently omits from the batch response are retried one by one."""
    a1 = Asset(symbol="AAPL", name="Apple", type=AssetType.STOCK, currency="USD")
    a2 = Asset(symbol="PRY.MI", name="Prysmian", type=AssetType.STOCK, currency="EUR")
    db.add_all([a1, a2])
    await db.commit()

    # Batch response only contains AAPL; PRY.MI must come from the per-symbol retry.
    mock_prov = _mock_provider(batch_fetch_history={"AAPL": _make_df()})
    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=10), \
         caplog.at_level(logging.WARNING, logger="app.services.price_sync"):
        counts = await sync_all_prices(db, period="1y")

    mock_prov.fetch_history.assert_awaited_once_with("PRY.MI", period="1y")
    assert counts == {"AAPL": 10, "PRY.MI": 10}
    assert "PRY.MI" in caplog.text


async def test_sync_all_no_retry_when_batch_entirely_empty(db, caplog):
    """A fully empty batch (breaker open / Yahoo down) is not retried per symbol."""
    a1 = Asset(symbol="AAPL", name="Apple", type=AssetType.STOCK, currency="USD")
    a2 = Asset(symbol="MSFT", name="Microsoft", type=AssetType.STOCK, currency="USD")
    db.add_all([a1, a2])
    await db.commit()

    mock_prov = _mock_provider(batch_fetch_history={})
    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=10), \
         caplog.at_level(logging.ERROR, logger="app.services.price_sync"):
        counts = await sync_all_prices(db)

    mock_prov.fetch_history.assert_not_awaited()
    assert counts == {}
    assert "no data" in caplog.text


async def test_sync_all_retry_failure_is_non_fatal(db):
    """A failing per-symbol retry doesn't abort the sync of other symbols."""
    a1 = Asset(symbol="AAPL", name="Apple", type=AssetType.STOCK, currency="USD")
    a2 = Asset(symbol="KOG.OL", name="Kongsberg", type=AssetType.STOCK, currency="NOK")
    db.add_all([a1, a2])
    await db.commit()

    mock_prov = _mock_provider(batch_fetch_history={"AAPL": _make_df()})
    mock_prov.fetch_history = AsyncMock(side_effect=Exception("boom"))
    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=10):
        counts = await sync_all_prices(db)

    assert counts == {"AAPL": 10}


async def test_sync_all_main_loop_failure_is_non_fatal(db):
    """A symbol raising during persist in the main batch loop doesn't abort the
    rest of the run, and its half-applied transaction is rolled back so it can't
    poison the symbols that follow it on the shared session."""
    db.add_all([
        Asset(symbol="BAD", name="Bad", type=AssetType.STOCK, currency="USD"),
        Asset(symbol="GOOD", name="Good", type=AssetType.STOCK, currency="USD"),
    ])
    await db.commit()

    async def fake_persist(_db, ref, _df, _anchor):
        if ref.symbol == "BAD":
            raise RuntimeError("boom")
        return 10

    # "BAD" is ordered before "GOOD" in the batch, so GOOD only syncs if the loop
    # survives BAD's failure rather than aborting on it.
    mock_prov = _mock_provider(batch_fetch_history={"BAD": _make_df(), "GOOD": _make_df()})
    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._drop_and_persist", side_effect=fake_persist), \
         patch.object(db, "rollback", new_callable=AsyncMock) as mock_rollback:
        counts = await sync_all_prices(db, period="1y")

    assert counts == {"GOOD": 10}
    assert "BAD" not in counts
    mock_rollback.assert_awaited_once()


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


async def test_drop_unsettled_logs_closed_market_lag(caplog):
    """Dropping a closed session's lagging bar is logged with the symbol.

    This is the path that leaves a symbol without its latest session's bar —
    the state the heal job repairs — so it must be diagnosable from logs.
    """
    df = _df_from_closes([130.0, 133.35, 137.0])
    with caplog.at_level(logging.INFO, logger="app.services.price_sync"):
        out = drop_unsettled_last_bar(df, 137.85, 133.35, "POSTPOST", symbol="PRY.MI")
    assert len(out) == len(df) - 1
    assert "PRY.MI" in caplog.text
    assert "settled" in caplog.text


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
    quotes = [Quote(**{"symbol": "IBM", "price": 220.84, "previous_close": 290.23,
               "market_state": "REGULAR"})]
    mock_prov = _mock_provider(batch_fetch_history=mock_data, batch_fetch_quotes=quotes)

    captured = {}

    async def _capture(*args):
        df = args[2]
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
    quotes = [Quote(**{"symbol": "MT.AS", "price": 58.72, "previous_close": 58.04,
               "market_state": "POSTPOST"})]
    mock_prov = _mock_provider(batch_fetch_history=mock_data, batch_fetch_quotes=quotes)

    captured = {}

    async def _capture(*args):
        captured["len"] = len(args[2])
        return len(args[2])

    with patch("app.services.price_sync.get_price_provider", return_value=mock_prov), \
         patch("app.services.price_sync._upsert_prices", side_effect=_capture):
        await sync_all_prices(db, period="1y")

    assert captured["len"] == 3  # nothing dropped


# --- drop_unsettled_last_bar: session-date guard (mid-session Yahoo lag) ---
#
# When Yahoo hasn't appended today's forming bar yet, the trailing row is a
# *completed* prior session whose own predecessor can coincidentally fall within
# tol of previous_close (a flat prior day). The close heuristic alone would drop
# that real bar; the session date keeps it.

async def test_drop_unsettled_keeps_completed_bar_before_session():
    """A trailing bar dated before the live session is completed → kept, even
    when its predecessor reconciles with previous_close (the flat-day misfire)."""
    # Last bar (100.0) is yesterday; predecessor (99.8) is within 0.5% of the
    # quote's previous_close (100.0) — the exact coincidence that misfires.
    df = _df_from_closes([100.0, 99.8, 100.0])
    session_date = date(2025, 1, 7)  # after the last bar's date (2025-01-06)
    out = drop_unsettled_last_bar(
        df, price=102.0, previous_close=100.0, market_state="REGULAR",
        session_date=session_date,
    )
    assert len(out) == len(df)  # kept — it is a completed prior session

    # Without the session date the close heuristic can't tell and drops it —
    # this is the latent bug the guard closes.
    out_no_date = drop_unsettled_last_bar(df, 102.0, 100.0, "REGULAR")
    assert len(out_no_date) == len(df) - 1


async def test_drop_unsettled_drops_forming_bar_on_session_date():
    """A trailing bar dated on the live session is the forming bar → still dropped."""
    df = _df_from_closes([305.0, 290.23, 224.14])
    out = drop_unsettled_last_bar(
        df, price=220.84, previous_close=290.23, market_state="REGULAR",
        session_date=date(2025, 1, 6),  # == the last bar's date
    )
    assert len(out) == len(df) - 1
    assert float(out.iloc[-1]["close"]) == 290.23


# --- anchorless guard (#586): no quote → withhold a possible live partial ---
#
# Observed 2026-08-05 on staging: a failed quote batch during EU market hours
# made every open-market symbol store its live forming bar as that session's
# close. Without an anchor the trailing bar dated on the venue's current local
# date is withheld; everything earlier is settled and stores as usual.

def _df_ending(end, closes):
    """OHLCV frame whose last bar is dated ``end`` (consecutive calendar days)."""
    n = len(closes)
    dates = pd.DatetimeIndex([pd.Timestamp(end) - pd.Timedelta(days=n - 1 - i)
                              for i in range(n)])
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1_000_000] * n,
    }, index=dates)


async def test_anchorless_withholds_current_session_bar():
    """A trailing bar dated today (no venue → server date) is withheld."""
    # A plain str ref has no venue, so the guard falls back to date.today().
    df = _df_ending(date.today(), [100.0, 101.0, 102.0])
    out = _drop_unanchored_trailing_bar(df, "NOVENUE")
    assert len(out) == len(df) - 1
    assert float(out.iloc[-1]["close"]) == 101.0


async def test_anchorless_keeps_settled_bars():
    """A frame ending before today is all settled — nothing withheld."""
    # Two days back: behind "today" in every venue timezone, so the assertion
    # can't flake around midnight for a venue-resolved ref either.
    df = _df_ending(date.today() - pd.Timedelta(days=2), [100.0, 101.0, 102.0])
    assert len(_drop_unanchored_trailing_bar(df, "NOVENUE")) == len(df)
    assert len(_drop_unanchored_trailing_bar(df, AssetRef("AAPL"))) == len(df)


async def test_anchorless_empty_frame():
    assert _drop_unanchored_trailing_bar(pd.DataFrame(), "NOVENUE").empty


async def test_anchorless_persist_withholds_and_never_purges(db):
    """_drop_and_persist without an anchor drops today's bar from the upsert but
    leaves stored rows alone — without a quote a later stored row can't be
    proven stale, and purging on every quote outage would destroy verified data."""
    asset = Asset(symbol="AAPL", name="Apple", type=AssetType.STOCK, currency="USD")
    db.add(asset)
    await db.flush()
    # A stored row dated after everything the anchorless upsert will keep.
    db.add(PriceHistory(asset_id=asset.id, date=date.today(),
                        open=1, high=1, low=1, close=500.0, volume=0))
    await db.commit()

    # Bar dated the server's today is >= the venue-local (NY) date, so the
    # withhold fires regardless of the hour the test runs at.
    df = _df_ending(date.today(), [305.0, 290.23, 224.14])

    captured = {}

    async def _capture(*args):
        captured["len"] = len(args[2])
        return len(args[2])

    with patch("app.services.price_sync._upsert_prices", side_effect=_capture):
        await _drop_and_persist(db, AssetRef.of(asset), df, _NO_ANCHOR)

    assert captured["len"] == 2  # today's bar withheld
    latest = await PriceRepository(db).get_latest_closes([asset.id])
    assert latest[asset.id][0] == date.today()  # stored row untouched


# --- _drop_and_persist: purge an orphaned partial a re-sync can't upsert away ---

async def test_drop_and_persist_deletes_orphaned_partial(db):
    """When a bar is dropped, a stale partial persisted past it is purged, so an
    upsert-only re-sync can't leave σ-Move blank all session."""
    asset = Asset(symbol="ORPH", name="Orphan", type=AssetType.STOCK, currency="USD")
    db.add(asset)
    await db.flush()
    # A leftover partial at a later date than anything the fetch will keep.
    db.add(PriceHistory(asset_id=asset.id, date=date(2025, 6, 30),
                        open=1, high=1, low=1, close=999.0, volume=0))
    await db.commit()

    # Fetched frame's last bar is a forming partial (predecessor == previous_close),
    # so drop_unsettled removes it; kept ends at an early-January date.
    df = _df_from_closes([305.0, 290.23, 224.14])
    anchor = (220.84, 290.23, "REGULAR", None)
    with patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=2):
        await _drop_and_persist(db, AssetRef.of(asset), df, anchor)

    latest = await PriceRepository(db).get_latest_closes([asset.id])
    assert asset.id not in latest  # the orphaned 2025-06-30 partial was deleted


async def test_drop_and_persist_keeps_rows_when_nothing_dropped(db):
    """No drop → no delete: a settled frame leaves later stored rows untouched."""
    asset = Asset(symbol="KEEP", name="Keep", type=AssetType.STOCK, currency="USD")
    db.add(asset)
    await db.flush()
    db.add(PriceHistory(asset_id=asset.id, date=date(2025, 6, 30),
                        open=1, high=1, low=1, close=500.0, volume=0))
    await db.commit()

    # Closed, settled bar (matches live price) → drop_unsettled keeps everything.
    df = _df_from_closes([57.5, 58.04, 59.0])
    anchor = (58.72, 58.04, "POSTPOST", None)
    with patch("app.services.price_sync._upsert_prices", new_callable=AsyncMock, return_value=3):
        await _drop_and_persist(db, AssetRef.of(asset), df, anchor)

    latest = await PriceRepository(db).get_latest_closes([asset.id])
    assert latest[asset.id][0] == date(2025, 6, 30)  # untouched

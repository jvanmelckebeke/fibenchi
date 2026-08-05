"""Tests for the price self-heal service.

``heal_unreconciled_prices`` refreshes grouped assets whose latest stored bar
reconciles with neither the live quote price nor its previous close — the
exact condition under which the frontend blanks σ-Move.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.price_repo import PriceRepository
from app.services import price_heal
from app.services.price_heal import MAX_HEALS_PER_RUN, heal_unreconciled_prices
from tests.helpers import seed_asset_with_prices

pytestmark = pytest.mark.asyncio(loop_scope="function")


@pytest.fixture(autouse=True)
def _reset_cooldowns():
    price_heal._last_attempt.clear()
    yield
    price_heal._last_attempt.clear()


def _provider_with_quotes(quotes):
    provider = MagicMock()
    provider.batch_fetch_quotes = AsyncMock(return_value=quotes)
    return provider


def _quote(symbol, price, prev, state="REGULAR"):
    return {
        "symbol": symbol, "price": price,
        "previous_close": prev, "market_state": state,
    }


async def _latest_close(db, asset) -> float:
    latest = await PriceRepository(db).get_latest_closes([asset.id])
    return latest[asset.id][1]


async def test_heal_refreshes_unreconciled_asset(db):
    """A stored close matching neither price nor previous_close gets refreshed."""
    asset = await seed_asset_with_prices(db, "PRY.MI", n_days=30)
    close = await _latest_close(db, asset)

    # Quote two sessions ahead of the stored bar: nothing reconciles.
    provider = _provider_with_quotes([_quote("PRY.MI", close * 0.90, close * 0.95)])
    with patch("app.services.price_heal.get_price_provider", return_value=provider), \
         patch("app.services.price_heal.sync_asset_prices",
               new_callable=AsyncMock, return_value=22) as mock_sync:
        healed = await heal_unreconciled_prices(db)

    assert healed == {"PRY.MI": 22}
    # The heal threads the already-fetched quote anchor into the sync so it
    # doesn't re-fetch the same quote (#5): (price, previous_close, state, date).
    mock_sync.assert_awaited_once_with(
        db, AssetRef.of(asset), period="1mo", anchor=(close * 0.90, close * 0.95, "REGULAR", None),
    )


async def test_heal_failure_is_non_fatal_and_rolls_back(db):
    """A heal that raises doesn't abort the others, and its half-applied
    transaction is rolled back so the shared session stays usable for the
    remaining symbols."""
    good = await seed_asset_with_prices(db, "GOOD.OL", n_days=30)
    bad = await seed_asset_with_prices(db, "BAD.OL", n_days=30)
    good_close = await _latest_close(db, good)
    bad_close = await _latest_close(db, bad)

    # Both quotes sit two sessions ahead of the stored bar: nothing reconciles,
    # so both are due for a heal.
    provider = _provider_with_quotes([
        _quote("GOOD.OL", good_close * 0.90, good_close * 0.95),
        _quote("BAD.OL", bad_close * 0.90, bad_close * 0.95),
    ])

    async def fake_sync(_db, asset, **_kw):
        if asset.symbol == "BAD.OL":
            raise RuntimeError("boom")
        return 22

    with patch("app.services.price_heal.get_price_provider", return_value=provider), \
         patch("app.services.price_heal.sync_asset_prices", side_effect=fake_sync), \
         patch.object(db, "rollback", new_callable=AsyncMock) as mock_rollback:
        healed = await heal_unreconciled_prices(db)

    assert healed == {"GOOD.OL": 22}
    assert "BAD.OL" not in healed
    mock_rollback.assert_awaited_once()


async def test_heal_skips_reconciling_assets(db):
    """Assets whose stored bar matches price or previous_close are left alone."""
    a1 = await seed_asset_with_prices(db, "PREV", n_days=30)
    a2 = await seed_asset_with_prices(db, "CURR", n_days=30)
    c1 = await _latest_close(db, a1)
    c2 = await _latest_close(db, a2)

    provider = _provider_with_quotes([
        # Normal market-hours state: stored bar is the quote's prior session.
        _quote("PREV", c1 * 0.95, c1),
        # Current session already stored (settled close equals the price).
        _quote("CURR", c2, c2 * 1.05),
    ])
    with patch("app.services.price_heal.get_price_provider", return_value=provider), \
         patch("app.services.price_heal.sync_asset_prices", new_callable=AsyncMock) as mock_sync:
        healed = await heal_unreconciled_prices(db)

    assert healed == {}
    mock_sync.assert_not_awaited()


async def test_heal_skips_assets_without_stored_bars(db):
    """No stored bars → initial fill is the sync's job, not the heal loop's."""
    await seed_asset_with_prices(db, "NEWB", n_days=0)

    provider = _provider_with_quotes([_quote("NEWB", 100.0, 99.0)])
    with patch("app.services.price_heal.get_price_provider", return_value=provider), \
         patch("app.services.price_heal.sync_asset_prices", new_callable=AsyncMock) as mock_sync:
        healed = await heal_unreconciled_prices(db)

    assert healed == {}
    mock_sync.assert_not_awaited()


async def test_heal_skips_dead_quotes(db):
    """A quote with neither price nor previous_close can't anchor a comparison."""
    await seed_asset_with_prices(db, "DEAD", n_days=30)

    provider = _provider_with_quotes([_quote("DEAD", None, None)])
    with patch("app.services.price_heal.get_price_provider", return_value=provider), \
         patch("app.services.price_heal.sync_asset_prices", new_callable=AsyncMock) as mock_sync:
        healed = await heal_unreconciled_prices(db)

    assert healed == {}
    mock_sync.assert_not_awaited()


async def test_heal_cooldown_prevents_hammering(db):
    """A symbol healed once is not re-attempted within the cooldown window."""
    seed = await seed_asset_with_prices(db, "LAG.MI", n_days=30)
    close = await _latest_close(db, seed)

    # Still unreconcilable after the heal (Yahoo keeps serving lagged data).
    provider = _provider_with_quotes([_quote("LAG.MI", close * 0.90, close * 0.95)])
    with patch("app.services.price_heal.get_price_provider", return_value=provider), \
         patch("app.services.price_heal.sync_asset_prices",
               new_callable=AsyncMock, return_value=0) as mock_sync:
        await heal_unreconciled_prices(db)
        await heal_unreconciled_prices(db)

    mock_sync.assert_awaited_once()


async def test_heal_caps_per_run_and_defers_rest(db):
    """At most MAX_HEALS_PER_RUN symbols are refreshed per run; the rest follow."""
    n = MAX_HEALS_PER_RUN + 2
    assets = [await seed_asset_with_prices(db, f"S{i:02d}", n_days=10) for i in range(n)]
    closes = {a.symbol: await _latest_close(db, a) for a in assets}

    provider = _provider_with_quotes(
        [_quote(s, c * 0.90, c * 0.95) for s, c in closes.items()]
    )
    with patch("app.services.price_heal.get_price_provider", return_value=provider), \
         patch("app.services.price_heal.sync_asset_prices",
               new_callable=AsyncMock, return_value=1) as mock_sync:
        first = await heal_unreconciled_prices(db)
        second = await heal_unreconciled_prices(db)

    assert len(first) == MAX_HEALS_PER_RUN
    assert len(second) == 2  # deferred symbols healed next run, not lost
    assert mock_sync.await_count == n


# ---------------------------------------------------------------------------
# Interior-hole heal (issue #559 fix 3)
# ---------------------------------------------------------------------------

from datetime import date, timedelta  # noqa: E402

from sqlalchemy import delete  # noqa: E402

from app.domain import AssetRef  # noqa: E402
from app.models import PriceHistory  # noqa: E402
from app.services.price_heal import find_interior_holes, heal_interior_holes  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_hole_state():
    price_heal._hole_attempts.clear()
    price_heal._last_hole_scan = None
    yield
    price_heal._hole_attempts.clear()
    price_heal._last_hole_scan = None


def test_find_interior_holes_strictly_inside():
    """Only mid-series misses count — leading/trailing gaps are other jobs'."""
    d = date(2026, 8, 3)
    stored = {d, d + timedelta(days=2), d + timedelta(days=4)}
    sessions = {d + timedelta(days=i) for i in range(-2, 7)}
    holes = find_interior_holes(stored, sessions)
    assert holes == {d + timedelta(days=1), d + timedelta(days=3)}


def test_find_interior_holes_empty_inputs():
    assert find_interior_holes(set(), {date(2026, 8, 3)}) == set()
    assert find_interior_holes({date(2026, 8, 3)}, set()) == set()


async def _seed_with_hole(db, symbol="AAPL"):
    """Seed a US asset and delete one real mid-window session's bar."""
    asset = await seed_asset_with_prices(db, symbol, n_days=60)
    stored = {p.date for p in await PriceRepository(db).list_by_asset(asset.id)}
    sessions = sorted(AssetRef(symbol).venue.session_dates(min(stored), max(stored)))
    hole = sessions[len(sessions) // 2]
    await db.execute(delete(PriceHistory).where(
        PriceHistory.asset_id == asset.id, PriceHistory.date == hole,
    ))
    await db.commit()
    return asset, hole


async def test_hole_heal_detects_and_refetches(db):
    """A deleted mid-series session is detected and its range re-fetched."""
    asset, hole = await _seed_with_hole(db)
    with patch.object(price_heal, "sync_asset_prices_range", new_callable=AsyncMock) as sync:
        sync.return_value = 1
        healed = await heal_interior_holes(db, force=True)
    assert healed == {asset.symbol: 1}
    sync.assert_awaited_once()
    _, called_asset, start, end = sync.await_args.args
    assert called_asset.id == asset.id
    assert start == end == hole


async def test_hole_heal_clean_series_no_fetch(db):
    """Seeded weekday bars (holidays included as extra rows) yield no holes —
    an exchange holiday must never be treated as missing data."""
    await seed_asset_with_prices(db, "AAPL", n_days=60)
    with patch.object(price_heal, "sync_asset_prices_range", new_callable=AsyncMock) as sync:
        healed = await heal_interior_holes(db, force=True)
    assert healed == {}
    sync.assert_not_awaited()


async def test_hole_heal_cooldown_same_holes(db):
    """The same unfilled hole set is not re-fetched within the retry cooldown."""
    await _seed_with_hole(db)
    with patch.object(price_heal, "sync_asset_prices_range", new_callable=AsyncMock) as sync:
        sync.return_value = 0
        first = await heal_interior_holes(db, force=True)
        second = await heal_interior_holes(db, force=True)
    assert first and second == {}
    sync.assert_awaited_once()


async def test_hole_heal_scan_interval_throttles(db):
    """Without force, a scan only runs once per HOLE_SCAN_INTERVAL_SECONDS."""
    await _seed_with_hole(db)
    with patch.object(price_heal, "sync_asset_prices_range", new_callable=AsyncMock) as sync:
        sync.return_value = 1
        first = await heal_interior_holes(db)
        second = await heal_interior_holes(db)
    assert first != {} and second == {}
    sync.assert_awaited_once()


async def test_hole_heal_failure_does_not_abort_batch(db):
    """One symbol's failed re-fetch must not kill the rest of the scan.

    Staging regression (2026-08-05): AIFS.DE raised "No data found", the
    rollback in the except path expired every ORM instance in the session,
    and the next candidate's attribute access crashed the whole job with
    MissingGreenlet — remaining candidates were never attempted.
    """
    await _seed_with_hole(db, "AAAA")
    await _seed_with_hole(db, "BBBB")

    async def sync_side_effect(db_, asset, start, end):
        if asset.symbol == "AAAA":
            raise ValueError("No data found for AAAA")
        return 1

    with patch.object(price_heal, "sync_asset_prices_range",
                      new=AsyncMock(side_effect=sync_side_effect)) as sync:
        healed = await heal_interior_holes(db, force=True)

    assert sync.await_count == 2
    assert "AAAA" not in healed
    assert healed.get("BBBB") == 1
    # The failed symbol still lands on cooldown so it isn't retried every scan.
    assert "AAAA" in price_heal._hole_attempts


async def test_hole_heal_skips_unknown_venue(db):
    """No venue calendar → holes and holidays are indistinguishable → skip."""
    asset = await seed_asset_with_prices(db, "FOO.XX", n_days=60)
    stored = sorted({p.date for p in await PriceRepository(db).list_by_asset(asset.id)})
    await db.execute(delete(PriceHistory).where(
        PriceHistory.asset_id == asset.id, PriceHistory.date == stored[len(stored) // 2],
    ))
    await db.commit()
    with patch.object(price_heal, "sync_asset_prices_range", new_callable=AsyncMock) as sync:
        healed = await heal_interior_holes(db, force=True)
    assert healed == {}
    sync.assert_not_awaited()

"""Tests for the price self-heal service.

``heal_unreconciled_prices`` refreshes grouped assets whose latest stored bar
reconciles with neither the live quote price nor its previous close — the
exact condition under which the frontend blanks σ-Move.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import update

from app.background_tasks import price_heal
from app.background_tasks.price_heal import MAX_HEALS_PER_RUN, heal_unreconciled_prices
from app.models import PriceHistory
from app.repositories.price_repo import PriceRepository
from app.schemas.quote import Quote
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
    return Quote(symbol=symbol, price=price, previous_close=prev, market_state=state)


async def _latest_close(db, asset) -> float:
    latest = await PriceRepository(db).get_latest_closes([asset.id])
    return latest[asset.id][1]


async def test_heal_refreshes_unreconciled_asset(db):
    """A stored close matching neither price nor previous_close gets refreshed."""
    asset = await seed_asset_with_prices(db, "PRY.MI", n_days=30)
    close = await _latest_close(db, asset)

    # Quote two sessions ahead of the stored bar: nothing reconciles.
    provider = _provider_with_quotes([_quote("PRY.MI", close * 0.90, close * 0.95)])
    with patch("app.background_tasks.price_heal.get_price_provider", return_value=provider), \
         patch("app.background_tasks.price_heal.sync_asset_prices",
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

    with patch("app.background_tasks.price_heal.get_price_provider", return_value=provider), \
         patch("app.background_tasks.price_heal.sync_asset_prices", side_effect=fake_sync), \
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
    with patch("app.background_tasks.price_heal.get_price_provider", return_value=provider), \
         patch("app.background_tasks.price_heal.sync_asset_prices", new_callable=AsyncMock) as mock_sync:
        healed = await heal_unreconciled_prices(db)

    assert healed == {}
    mock_sync.assert_not_awaited()


async def test_heal_skips_assets_without_stored_bars(db):
    """No stored bars → initial fill is the sync's job, not the heal loop's."""
    await seed_asset_with_prices(db, "NEWB", n_days=0)

    provider = _provider_with_quotes([_quote("NEWB", 100.0, 99.0)])
    with patch("app.background_tasks.price_heal.get_price_provider", return_value=provider), \
         patch("app.background_tasks.price_heal.sync_asset_prices", new_callable=AsyncMock) as mock_sync:
        healed = await heal_unreconciled_prices(db)

    assert healed == {}
    mock_sync.assert_not_awaited()


async def test_heal_skips_dead_quotes(db):
    """A quote with neither price nor previous_close can't anchor a comparison."""
    await seed_asset_with_prices(db, "DEAD", n_days=30)

    provider = _provider_with_quotes([_quote("DEAD", None, None)])
    with patch("app.background_tasks.price_heal.get_price_provider", return_value=provider), \
         patch("app.background_tasks.price_heal.sync_asset_prices", new_callable=AsyncMock) as mock_sync:
        healed = await heal_unreconciled_prices(db)

    assert healed == {}
    mock_sync.assert_not_awaited()


async def test_heal_cooldown_prevents_hammering(db):
    """A symbol healed once is not re-attempted within the cooldown window."""
    seed = await seed_asset_with_prices(db, "LAG.MI", n_days=30)
    close = await _latest_close(db, seed)

    # Still unreconcilable after the heal (Yahoo keeps serving lagged data).
    provider = _provider_with_quotes([_quote("LAG.MI", close * 0.90, close * 0.95)])
    with patch("app.background_tasks.price_heal.get_price_provider", return_value=provider), \
         patch("app.background_tasks.price_heal.sync_asset_prices",
               new_callable=AsyncMock, return_value=0) as mock_sync:
        await heal_unreconciled_prices(db)
        await heal_unreconciled_prices(db)

    mock_sync.assert_awaited_once()


async def test_heal_success_does_not_burn_the_cooldown(db):
    """The 30-minute lockout exists for "Yahoo is serving unreconcilable data".
    A heal that actually repaired the symbol must not buy it: before #627 the
    cooldown was charged on the *attempt*, so a heal that structurally could
    not work (the orphan purge never fired) locked the symbol out every run
    while changing nothing."""
    asset = await seed_asset_with_prices(db, "FIXD.MI", n_days=30)
    close = await _latest_close(db, asset)
    fixed_price = close * 0.90
    provider = _provider_with_quotes([_quote("FIXD.MI", fixed_price, close * 0.95)])

    async def repairing_sync(session, ref, period=None, anchor=None):
        """Stand in for a sync that genuinely fixes the stored bar."""
        latest = await PriceRepository(session).get_latest_closes([ref.id])
        await session.execute(
            update(PriceHistory)
            .where(PriceHistory.asset_id == ref.id, PriceHistory.date == latest[ref.id][0])
            .values(close=fixed_price)
        )
        await session.commit()
        return 1

    with patch("app.background_tasks.price_heal.get_price_provider", return_value=provider), \
         patch("app.background_tasks.price_heal.sync_asset_prices", side_effect=repairing_sync):
        await heal_unreconciled_prices(db)

    assert await _latest_close(db, asset) == pytest.approx(fixed_price)
    assert "FIXD.MI" not in price_heal._last_attempt


async def test_heal_error_still_sets_the_cooldown(db):
    """A symbol whose refresh raises must still back off, or a persistently
    failing symbol is retried every run."""
    asset = await seed_asset_with_prices(db, "BOOM.MI", n_days=30)
    close = await _latest_close(db, asset)
    provider = _provider_with_quotes([_quote("BOOM.MI", close * 0.90, close * 0.95)])

    with patch("app.background_tasks.price_heal.get_price_provider", return_value=provider), \
         patch("app.background_tasks.price_heal.sync_asset_prices",
               new_callable=AsyncMock, side_effect=RuntimeError("yahoo down")):
        healed = await heal_unreconciled_prices(db)

    assert healed == {}
    assert "BOOM.MI" in price_heal._last_attempt


async def test_heal_caps_per_run_and_defers_rest(db):
    """At most MAX_HEALS_PER_RUN symbols are refreshed per run; the rest follow."""
    n = MAX_HEALS_PER_RUN + 2
    assets = [await seed_asset_with_prices(db, f"S{i:02d}", n_days=10) for i in range(n)]
    closes = {a.symbol: await _latest_close(db, a) for a in assets}

    provider = _provider_with_quotes(
        [_quote(s, c * 0.90, c * 0.95) for s, c in closes.items()]
    )
    with patch("app.background_tasks.price_heal.get_price_provider", return_value=provider), \
         patch("app.background_tasks.price_heal.sync_asset_prices",
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

from app.background_tasks.price_heal import find_interior_holes, heal_interior_holes  # noqa: E402
from app.domain import AssetRef  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_hole_state():
    price_heal._hole_attempts.clear()
    price_heal._last_hole_scan = None
    price_heal._hole_backlog = False
    yield
    price_heal._hole_attempts.clear()
    price_heal._last_hole_scan = None
    price_heal._hole_backlog = False


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


async def _seed_with_hole(db, symbol="AAPL", frac=0.5):
    """Seed a US asset and delete one real interior session's bar.

    ``frac`` places the hole within the stored range (0 = oldest end,
    1 = newest end); always strictly interior.
    """
    asset = await seed_asset_with_prices(db, symbol, n_days=60)
    stored = {p.date for p in await PriceRepository(db).list_by_asset(asset.id)}
    sessions = sorted(AssetRef(symbol).venue.session_dates(min(stored), max(stored)))
    hole = sessions[max(1, min(len(sessions) - 2, int(len(sessions) * frac)))]
    await db.execute(delete(PriceHistory).where(
        PriceHistory.asset_id == asset.id, PriceHistory.date == hole,
    ))
    await db.commit()
    return asset, hole


async def test_hole_heal_detects_and_refetches(db):
    """A deleted mid-series session is detected and re-fetched with a padded
    range: Yahoo's exclusive ``end`` means the newest hole must sit strictly
    inside the requested window (staging regression 2026-08-05: fetching
    exactly ``min(holes)..max(holes)`` never requested the newest hole, and
    single-hole symbols asked for an empty range — "No data found")."""
    asset, hole = await _seed_with_hole(db)
    with patch.object(price_heal, "sync_asset_prices_range", new_callable=AsyncMock) as sync:
        sync.return_value = 1
        healed = await heal_interior_holes(db, force=True)
    assert healed == {asset.symbol: 1}
    sync.assert_awaited_once()
    _, called_asset, start, end = sync.await_args.args
    assert called_asset.id == asset.id
    assert start == hole - timedelta(days=5)
    assert end == hole + timedelta(days=1)


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


async def test_hole_heal_prioritizes_newest_holes(db):
    """When the per-scan cap forces a choice, the symbol whose hole is most
    recent goes first — a hole at yesterday's session blanks σ-Move *today*,
    an old interior hole only dents historical charts."""
    await _seed_with_hole(db, "OLDH", frac=0.2)
    await _seed_with_hole(db, "NEWH", frac=0.8)
    with (
        patch.object(price_heal, "MAX_HOLE_HEALS_PER_SCAN", 1),
        patch.object(price_heal, "sync_asset_prices_range", new_callable=AsyncMock) as sync,
    ):
        sync.return_value = 1
        healed = await heal_interior_holes(db, force=True)
    assert list(healed) == ["NEWH"]
    assert price_heal._hole_backlog is True


async def test_hole_heal_backlog_rescans_sooner(db):
    """A capped scan leaves unattempted symbols; the next scan then runs after
    the short backlog interval instead of the full one, and the backlog flag
    clears once nothing is deferred (2026-08-05: a feed-wide NaN session hit
    dozens of symbols at once — at the old fixed 6h cadence the tail waited
    days)."""
    await _seed_with_hole(db, "AAAA")
    await _seed_with_hole(db, "BBBB")
    with (
        patch.object(price_heal, "MAX_HOLE_HEALS_PER_SCAN", 1),
        patch.object(price_heal, "sync_asset_prices_range", new_callable=AsyncMock) as sync,
    ):
        sync.return_value = 1
        first = await heal_interior_holes(db)
        assert len(first) == 1
        assert price_heal._hole_backlog is True

        # Immediately after: still throttled, even in backlog mode.
        assert await heal_interior_holes(db) == {}

        # Past the backlog interval (but far inside the normal 6h one): the
        # deferred symbol is attempted. The first symbol sits on the retry
        # cooldown (its mocked "heal" filled nothing), so it doesn't recount.
        price_heal._last_hole_scan -= price_heal.HOLE_BACKLOG_RESCAN_SECONDS + 1
        second = await heal_interior_holes(db)
        assert len(second) == 1
        assert set(first) != set(second)
        assert price_heal._hole_backlog is False


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

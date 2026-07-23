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
        db, asset, period="1mo", anchor=(close * 0.90, close * 0.95, "REGULAR", None),
    )


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

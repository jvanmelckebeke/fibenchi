"""Detecting and repairing a stored series that changes share basis (#648)."""

from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from app.background_tasks import split_heal
from app.background_tasks.split_heal import heal_split_discontinuities
from app.models import Asset, AssetType, PriceHistory
from app.repositories.price_repo import PriceRepository

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _asset(db, symbol: str, closes: list[float]) -> Asset:
    """Store one asset with ``closes`` on consecutive days, oldest first."""
    asset = Asset(symbol=symbol, name=f"{symbol} Inc.", type=AssetType.STOCK, currency="USD")
    db.add(asset)
    await db.flush()
    start = date(2026, 1, 5)
    for i, c in enumerate(closes):
        db.add(PriceHistory(
            asset_id=asset.id, date=start + timedelta(days=i),
            open=c, high=c * 1.01, low=c * 0.99, close=c, volume=1_000_000,
        ))
    await db.commit()
    return asset


@pytest.fixture(autouse=True)
def _forget_unexplained():
    """The memo is process-wide, so tests must not inherit each other's."""
    split_heal._unexplained.clear()
    yield
    split_heal._unexplained.clear()


class TestDetection:
    async def test_finds_the_later_bar_of_a_split_sized_step(self, db):
        asset = await _asset(db, "MNST", [94.4, 91.43, 45.53, 46.0])
        steps = await PriceRepository(db).find_price_steps(1.4)

        assert len(steps) == 1
        asset_id, boundary, prev_close, close = steps[0]
        assert asset_id == asset.id
        assert boundary == date(2026, 1, 7)
        assert (prev_close, close) == (91.43, 45.53)

    async def test_ignores_an_ordinary_bad_day(self, db):
        # IBM 2026-07-14, 290.23 -> 217.07. Real, and the threshold clears it.
        await _asset(db, "IBM", [295.3, 290.23, 217.07, 211.2])
        assert await PriceRepository(db).find_price_steps(1.4) == []

    async def test_finds_a_step_in_either_direction(self, db):
        await _asset(db, "UP", [10.0, 30.0])
        await _asset(db, "DOWN", [30.0, 10.0])
        assert len(await PriceRepository(db).find_price_steps(1.4)) == 2

    async def test_does_not_pair_bars_across_assets(self, db):
        # Without the partition, B's first bar would look like a step from A's
        # last one and every two-asset book would report a phantom split.
        await _asset(db, "A", [100.0, 101.0])
        await _asset(db, "B", [5.0, 5.1])
        assert await PriceRepository(db).find_price_steps(1.4) == []

    async def test_can_be_scoped_to_one_asset(self, db):
        await _asset(db, "A", [100.0, 40.0])
        b = await _asset(db, "B", [100.0, 40.0])
        steps = await PriceRepository(db).find_price_steps(1.4, asset_ids=[b.id])
        assert [s[0] for s in steps] == [b.id]


def _frame(closes: dict) -> pd.DataFrame:
    """A provider frame: {date: close}, already normalized by the fetch path."""
    vals = list(closes.values())
    return pd.DataFrame(
        {"open": vals, "high": vals, "low": vals, "close": vals,
         "volume": [1_000_000] * len(vals)},
        index=pd.Index(list(closes), name="date"),
    )


@contextmanager
def _provider(frame: pd.DataFrame | Exception, persist=None):
    """Stand in for the fetch + persist half of the heal.

    Persistence is ``_drop_and_persist``, shared with every other sync path and
    tested there; what this module owns is what happens around it.
    """
    calls: list[str] = []

    async def _fetch(ref, period="3mo", interval="1d", start=None, end=None):
        calls.append(str(ref))
        if isinstance(frame, Exception):
            raise frame
        return frame

    async def _store(session, ref, df, anchor):
        if persist is not None:
            await persist(session, ref, df)
        return len(df)

    with (
        patch.object(split_heal, "_drop_and_persist", side_effect=_store),
        patch.object(split_heal, "_quote_anchors", return_value={}),
        patch.object(split_heal, "get_price_provider") as get_provider,
    ):
        get_provider.return_value.fetch_history = _fetch
        yield calls


async def _apply(session, ref, df):
    """Write the frame's closes onto the stored rows it covers."""
    for row in await PriceRepository(session).list_by_asset(ref.id):
        if row.date in df.index:
            row.close = float(df.loc[row.date, "close"])
    await session.commit()


D = [date(2026, 1, 5) + timedelta(days=i) for i in range(5)]


class TestRepair:
    async def test_refetches_the_stored_span_and_reports_the_repair(self, db):
        asset = await _asset(db, "MNST", [94.4, 91.43, 45.53, 46.0])
        rebased = _frame({D[0]: 47.20, D[1]: 45.715, D[2]: 45.53, D[3]: 46.0})

        with _provider(rebased, persist=_apply):
            healed = await heal_split_discontinuities(db)

        assert healed == {"MNST": 4}
        assert await PriceRepository(db).find_price_steps(1.4, asset_ids=[asset.id]) == []

    async def test_the_window_covers_every_stored_bar(self, db):
        # period="max" would work and is the wrong choice: it writes decades we
        # never display, at a precision where sub-cent bars round into exact 2x
        # steps and manufacture fresh discontinuities.
        await _asset(db, "MNST", [94.4, 91.43, 45.53])
        seen = {}

        async def _fetch(ref, period="3mo", interval="1d", start=None, end=None):
            seen.update(period=period, start=start, end=end)
            return _frame({D[0]: 47.20, D[1]: 45.715, D[2]: 45.53})

        with (
            patch.object(split_heal, "_drop_and_persist", return_value=3),
            patch.object(split_heal, "_quote_anchors", return_value={}),
            patch.object(split_heal, "get_price_provider") as get_provider,
        ):
            get_provider.return_value.fetch_history = _fetch
            await heal_split_discontinuities(db)

        assert seen["start"] == D[0], "must reach the oldest bar we hold"
        assert seen["end"] > date.today()
        assert seen["period"] != "max"

    async def test_a_step_that_survives_a_refetch_is_not_retried(self, db):
        # OKLO's -54% SPAC reprice. The provider prices both bars, so no split
        # explains it, and without the memo the fetch would repeat every run.
        await _asset(db, "OKLO", [18.23, 8.45, 8.6])
        frame = _frame({D[0]: 18.23, D[1]: 8.45, D[2]: 8.6})

        with _provider(frame) as calls:
            assert await heal_split_discontinuities(db) == {}
            assert await heal_split_discontinuities(db) == {}

        assert calls == ["OKLO"]

    async def test_a_real_session_is_never_deleted(self, db):
        asset = await _asset(db, "OKLO", [18.23, 8.45, 8.6])
        with _provider(_frame({D[0]: 18.23, D[1]: 8.45, D[2]: 8.6})):
            await heal_split_discontinuities(db)
        assert len(await PriceRepository(db).list_by_asset(asset.id)) == 3

    async def test_a_failed_refetch_is_isolated_and_retried_later(self, db):
        # A provider error is not evidence about the step, so it must not be
        # memoized as unexplained the way a survived re-fetch is.
        await _asset(db, "MNST", [94.4, 91.43, 45.53])
        with _provider(RuntimeError("Yahoo said no")):
            assert await heal_split_discontinuities(db) == {}
        assert not split_heal._unexplained

    async def test_clean_book_does_no_work(self, db):
        await _asset(db, "AAPL", [100.0, 101.0, 102.0])
        with _provider(_frame({D[0]: 100.0})) as calls:
            assert await heal_split_discontinuities(db) == {}
        assert calls == []

    async def test_bounded_per_run(self, db):
        for i in range(split_heal.MAX_SPLIT_HEALS_PER_RUN + 3):
            await _asset(db, f"S{i}", [100.0, 40.0])
        with _provider(_frame({D[0]: 100.0, D[1]: 40.0})) as calls:
            await heal_split_discontinuities(db)
        assert len(calls) == split_heal.MAX_SPLIT_HEALS_PER_RUN


class TestUnrebasableBars:
    """A stored bar the provider has stopped pricing survives the re-fetch
    untouched, so after a rebasing it is the one row left in the old basis.
    MNST 2026-08-10: the whole history came back halved, our 91.43 did not, and
    the -50% step stayed exactly where it was.
    """

    async def test_the_orphan_is_removed_and_the_step_resolves(self, db):
        asset = await _asset(db, "MNST", [94.4, 90.36, 91.43, 45.53, 46.0])
        # The provider no longer prices D[2] at all, so the upsert cannot reach
        # the one bar that still needs halving.
        rebased = _frame({D[0]: 47.20, D[1]: 45.18, D[3]: 45.53, D[4]: 46.0})

        with _provider(rebased, persist=_apply):
            healed = await heal_split_discontinuities(db)

        assert "MNST" in healed
        stored = {p.date for p in await PriceRepository(db).list_by_asset(asset.id)}
        assert D[2] not in stored, "a bar that cannot be rebased must go, not lie"
        assert await PriceRepository(db).find_price_steps(1.4, asset_ids=[asset.id]) == []

    async def test_nothing_is_deleted_when_the_provider_prices_both_sides(self, db):
        asset = await _asset(db, "PL", [3.99, 5.96, 6.0])
        with _provider(_frame({D[0]: 3.99, D[1]: 5.96, D[2]: 6.0})):
            assert await heal_split_discontinuities(db) == {}
        assert len(await PriceRepository(db).list_by_asset(asset.id)) == 3

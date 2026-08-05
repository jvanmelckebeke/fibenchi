"""Tests for GET /api/system/data-health."""

import pytest
from sqlalchemy import delete, select

from app.background_tasks import price_heal
from app.domain import AssetRef
from app.models import PriceHistory
from app.repositories.price_repo import PriceRepository
from tests.helpers import seed_asset_with_prices

pytestmark = pytest.mark.asyncio(loop_scope="function")


@pytest.fixture(autouse=True)
def _reset_hole_state():
    price_heal._last_hole_scan = None
    price_heal._hole_backlog = False
    yield
    price_heal._last_hole_scan = None
    price_heal._hole_backlog = False


async def test_data_health_clean(client, db):
    """Complete series → no holes, next scan immediately eligible."""
    await seed_asset_with_prices(db, "AAPL", n_days=60)
    resp = await client.get("/api/system/data-health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["hole_symbols"] == []
    assert data["total_missing_sessions"] == 0
    assert data["covered_symbols"] == 1
    assert data["next_scan_in_seconds"] == 0  # never scanned yet
    assert data["heals_per_scan"] == price_heal.MAX_HOLE_HEALS_PER_SCAN


async def test_data_health_reports_holes(client, db):
    """A deleted mid-series session shows up with its date."""
    asset = await seed_asset_with_prices(db, "AAPL", n_days=60)
    stored = {p.date for p in await PriceRepository(db).list_by_asset(asset.id)}
    sessions = sorted(AssetRef("AAPL").venue.session_dates(min(stored), max(stored)))
    hole = sessions[len(sessions) // 2]
    await db.execute(delete(PriceHistory).where(
        PriceHistory.asset_id == asset.id, PriceHistory.date == hole,
    ))
    await db.commit()

    resp = await client.get("/api/system/data-health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_missing_sessions"] == 1
    assert data["hole_symbols"] == [
        {"symbol": "AAPL", "missing_sessions": [hole.isoformat()]}
    ]


async def test_data_health_next_scan_reflects_throttle(client, db):
    """After a scan, next_scan_in_seconds counts down from the scan interval."""
    await seed_asset_with_prices(db, "AAPL", n_days=60)
    await price_heal.heal_interior_holes(db, force=True)
    resp = await client.get("/api/system/data-health")
    secs = resp.json()["next_scan_in_seconds"]
    assert 0 < secs <= price_heal.HOLE_SCAN_INTERVAL_SECONDS


async def test_data_health_expected_bars_give_completeness(client, db):
    """expected_session_bars is the denominator: with one hole, completeness
    is (expected - 1) / expected."""
    asset = await seed_asset_with_prices(db, "AAPL", n_days=60)
    stored = {p.date for p in await PriceRepository(db).list_by_asset(asset.id)}
    sessions = sorted(AssetRef("AAPL").venue.session_dates(min(stored), max(stored)))
    await db.execute(delete(PriceHistory).where(
        PriceHistory.asset_id == asset.id,
        PriceHistory.date == sessions[len(sessions) // 2],
    ))
    await db.commit()

    data = (await client.get("/api/system/data-health")).json()
    assert data["expected_session_bars"] == len(sessions)
    assert data["total_missing_sessions"] == 1


async def test_stats_counts_collection(client, db):
    """Stats reports asset/bar counts and the collected span."""
    asset = await seed_asset_with_prices(db, "AAPL", n_days=60)
    prices = await PriceRepository(db).list_by_asset(asset.id)

    resp = await client.get("/api/system/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["assets_total"] == 1
    assert data["assets_tracked"] == 1
    assert data["price_bars"] == len(prices)
    assert data["earliest_bar"] == min(p.date for p in prices).isoformat()
    assert data["latest_bar"] == max(p.date for p in prices).isoformat()
    expected_span = (max(p.date for p in prices) - min(p.date for p in prices)).days + 1
    assert data["collected_days"] == expected_span
    assert data["groups"] >= 1  # seeded default Watchlist


async def test_stats_asset_mix_classifies_by_ticker_shape(client, db):
    """The asset mix combines ticker-shape kinds (crypto/futures) with the
    stored Yahoo type (stock vs ETF)."""
    await seed_asset_with_prices(db, "AAPL", n_days=40)      # stock
    await seed_asset_with_prices(db, "BTC-USD", n_days=40)   # crypto by shape
    await seed_asset_with_prices(db, "ES=F", n_days=40)      # future by shape

    data = (await client.get("/api/system/stats")).json()
    assert data["stocks"] == 1
    assert data["crypto"] == 1
    assert data["futures"] == 1
    assert data["etfs"] == 0
    assert data["assets_total"] == 3


async def test_stats_splits_ungrouped_by_reason(client, db):
    """Ungrouped assets split into thesis/pseudo-ETF-referenced vs orphaned."""
    from datetime import date as date_cls

    from sqlalchemy import insert

    from app.models.thesis import Thesis, thesis_assets

    await seed_asset_with_prices(db, "AAPL", n_days=40)  # grouped
    kept = await seed_asset_with_prices(db, "KEPT", n_days=40, add_to_group=False)
    await seed_asset_with_prices(db, "ORPH", n_days=40, add_to_group=False)

    thesis = Thesis(name="Kept by thesis", opened_at=date_cls.today())
    db.add(thesis)
    await db.flush()
    await db.execute(insert(thesis_assets).values(thesis_id=thesis.id, asset_id=kept.id))
    await db.commit()

    data = (await client.get("/api/system/stats")).json()
    assert data["assets_tracked"] == 1
    assert data["assets_thesis_or_etf_only"] == 1
    assert data["assets_orphaned"] == 1


async def test_orphans_listed_and_hard_deletable(client, db):
    """Orphans are listed with their deletion cost; DELETE removes row + bars."""
    orph = await seed_asset_with_prices(db, "ORPH", n_days=40, add_to_group=False)
    await seed_asset_with_prices(db, "AAPL", n_days=40)  # grouped — must not appear

    resp = await client.get("/api/system/orphans")
    assert resp.status_code == 200
    orphans = resp.json()
    assert [o["symbol"] for o in orphans] == ["ORPH"]
    assert orphans[0]["price_bars"] > 0
    assert orphans[0]["latest_bar"] is not None

    resp = await client.delete(f"/api/system/orphans/{orph.id}")
    assert resp.status_code == 204
    assert (await client.get("/api/system/orphans")).json() == []
    bars = (await db.execute(
        select(PriceHistory).where(PriceHistory.asset_id == orph.id)
    )).scalars().all()
    assert bars == []


async def test_orphan_delete_refuses_referenced_assets(client, db):
    """The hard delete must never remove a row something still uses."""
    grouped = await seed_asset_with_prices(db, "AAPL", n_days=40)
    resp = await client.delete(f"/api/system/orphans/{grouped.id}")
    assert resp.status_code == 409
    assert (await client.delete("/api/system/orphans/999999")).status_code == 404


async def test_stats_empty_db(client, db):
    """A fresh instance reports zeros, not a 500."""
    resp = await client.get("/api/system/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["assets_total"] == 0
    assert data["price_bars"] == 0
    assert data["earliest_bar"] is None
    assert data["collected_days"] == 0
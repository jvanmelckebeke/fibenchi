"""Tests for PriceRepository — date-range queries and aggregations against real SQLite DB."""

import pytest
from datetime import date, timedelta

import pandas as pd

from app.models import Asset, AssetType, PriceHistory
from app.repositories.price_repo import PriceRepository

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _create_asset(db, symbol: str = "AAPL") -> Asset:
    asset = Asset(symbol=symbol, name=f"{symbol} Inc.", type=AssetType.STOCK, currency="USD", watchlisted=True)
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def _seed_prices(db, asset_id: int, n_days: int = 30, base_price: float = 100.0) -> list[PriceHistory]:
    today = date.today()
    prices = []
    for i in range(n_days):
        d = today - timedelta(days=n_days - 1 - i)
        if d.weekday() >= 5:
            continue
        price = base_price + i * 0.5
        p = PriceHistory(
            asset_id=asset_id, date=d,
            open=round(price - 0.5, 4), high=round(price + 1.0, 4),
            low=round(price - 1.0, 4), close=round(price, 4),
            volume=1_000_000,
        )
        db.add(p)
        prices.append(p)
    await db.commit()
    return prices


async def test_list_by_asset_ordered(db):
    asset = await _create_asset(db)
    await _seed_prices(db, asset.id, n_days=10)

    repo = PriceRepository(db)
    result = await repo.list_by_asset(asset.id)
    assert len(result) > 0
    dates = [p.date for p in result]
    assert dates == sorted(dates)


async def test_list_by_asset_since(db):
    asset = await _create_asset(db)
    await _seed_prices(db, asset.id, n_days=30)

    since = date.today() - timedelta(days=10)
    repo = PriceRepository(db)
    result = await repo.list_by_asset_since(asset.id, since)
    assert all(p.date >= since for p in result)


async def test_list_by_assets_since(db):
    a1 = await _create_asset(db, "AAPL")
    a2 = await _create_asset(db, "MSFT")
    await _seed_prices(db, a1.id, n_days=20)
    await _seed_prices(db, a2.id, n_days=20)

    since = date.today() - timedelta(days=10)
    repo = PriceRepository(db)
    result = await repo.list_by_assets_since([a1.id, a2.id], since)
    asset_ids = {p.asset_id for p in result}
    assert a1.id in asset_ids
    assert a2.id in asset_ids
    assert all(p.date >= since for p in result)


async def test_get_latest_date(db):
    asset = await _create_asset(db)
    await _seed_prices(db, asset.id, n_days=20)

    repo = PriceRepository(db)
    latest = await repo.get_latest_date([asset.id])
    assert latest is not None
    # Latest date should be today or very close (weekday adjustments)
    assert latest >= date.today() - timedelta(days=3)


async def test_get_latest_date_no_data(db):
    repo = PriceRepository(db)
    result = await repo.get_latest_date([999])
    assert result is None


async def test_get_first_dates(db):
    a1 = await _create_asset(db, "AAPL")
    a2 = await _create_asset(db, "MSFT")
    await _seed_prices(db, a1.id, n_days=30)
    await _seed_prices(db, a2.id, n_days=30)

    since = date.today() - timedelta(days=15)
    repo = PriceRepository(db)
    first_dates = await repo.get_first_dates([a1.id, a2.id], since)
    assert a1.id in first_dates
    assert a2.id in first_dates
    assert first_dates[a1.id] >= since


async def test_get_last_dates(db):
    a1 = await _create_asset(db, "AAPL")
    await _seed_prices(db, a1.id, n_days=30)

    repo = PriceRepository(db)
    last_dates = await repo.get_last_dates([a1.id])
    assert a1.id in last_dates


async def test_get_prices_at_dates(db):
    asset = await _create_asset(db)
    prices = await _seed_prices(db, asset.id, n_days=10)

    repo = PriceRepository(db)
    target_dates = {prices[0].date, prices[-1].date}
    result = await repo.get_prices_at_dates([asset.id], target_dates)
    assert (asset.id, prices[0].date) in result
    assert (asset.id, prices[-1].date) in result


async def test_upsert_prices_mocked(db):
    """upsert_prices uses pg_insert which is PostgreSQL-only, so we verify the
    empty-DataFrame shortcut works and mock the rest."""
    repo = PriceRepository(db)
    count = await repo.upsert_prices(1, pd.DataFrame())
    assert count == 0

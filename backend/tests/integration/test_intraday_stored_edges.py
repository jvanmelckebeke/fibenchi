"""``IntradayRepository.load_stored_edges`` against a real Postgres.

The query is a per-asset LATERAL join, which SQLite can't run, so every other
intraday test patches it out. Needs MIGRATIONS_DATABASE_URL (CI's postgres
service). The tables live in a private schema, so the fresh-migrations test's
``DROP SCHEMA public`` can't touch them and they don't touch ``public``.
"""

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.asset import Asset, AssetType
from app.models.intraday import IntradayPrice
from app.repositories.intraday_repo import IntradayRepository

URL = os.environ.get("MIGRATIONS_DATABASE_URL")
SCHEMA = "intraday_edges_test"

pytestmark = pytest.mark.skipif(not URL, reason="needs MIGRATIONS_DATABASE_URL (a Postgres)")


def _ts(minute: int) -> datetime:
    return datetime(2026, 1, 5, 15, minute, tzinfo=timezone.utc)


async def test_each_asset_gets_its_own_oldest_and_newest_bar():
    engine = create_async_engine(URL, connect_args={"server_settings": {"search_path": SCHEMA}})
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        await conn.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        await conn.run_sync(Base.metadata.create_all, tables=[Asset.__table__, IntradayPrice.__table__])
    try:
        async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as db:
            bars = Asset(symbol="BARS", name="bars", type=AssetType.STOCK, currency="USD")
            null_volume = Asset(symbol="NULLVOL", name="null volume", type=AssetType.STOCK, currency="USD")
            empty = Asset(symbol="EMPTY", name="nothing stored", type=AssetType.STOCK, currency="USD")
            db.add_all([bars, null_volume, empty])
            await db.flush()
            db.add_all(
                [
                    # Bars span minutes 0-5 for one asset and 10-12 for the other, so a
                    # table-wide MIN/MAX (a dropped .lateral()) matches neither.
                    IntradayPrice(asset_id=bars.id, timestamp=_ts(m), price=100 + m, volume=10 * m, session="regular")
                    for m in (0, 3, 5)
                ]
                + [
                    IntradayPrice(asset_id=null_volume.id, timestamp=_ts(10), price=50, volume=7, session="pre"),
                    IntradayPrice(asset_id=null_volume.id, timestamp=_ts(12), price=51.5, volume=None, session="post"),
                ]
            )
            await db.commit()

            edges = await IntradayRepository(db).load_stored_edges([bars.id, null_volume.id, empty.id])

            assert set(edges) == {bars.id, null_volume.id}
            assert edges[bars.id].oldest == _ts(0)
            assert edges[bars.id].newest == _ts(5)
            assert edges[bars.id].newest_values == (105.0, 50, "regular")
            assert edges[null_volume.id].oldest == _ts(10)
            assert edges[null_volume.id].newest == _ts(12)
            assert edges[null_volume.id].newest_values == (51.5, 0, "post")
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA {SCHEMA} CASCADE"))
        await engine.dispose()

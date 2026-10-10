"""A fresh Postgres database built from the migrations alone.

Prod's database predates Alembic and never runs the early revisions, so only
a database built from scratch shows whether the migration chain still works.
Needs a real, empty Postgres: set MIGRATIONS_DATABASE_URL (CI does, with a
postgres service). Skipped otherwise, since SQLite can't exercise enum DDL.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.asset import Asset, AssetType

URL = os.environ.get("MIGRATIONS_DATABASE_URL")
BACKEND = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(not URL, reason="needs MIGRATIONS_DATABASE_URL (an empty Postgres)")


async def test_upgrade_head_builds_a_working_database():
    engine = create_async_engine(URL)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": URL},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr[-2000:]

    async with engine.connect() as conn:
        labels = (
            await conn.execute(
                text(
                    "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                    "WHERE t.typname = 'assettype'"
                )
            )
        ).scalars().all()
    # Enum(AssetType) writes member names, so every one of them must be a label.
    assert {t.name for t in AssetType} <= set(labels)

    session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session() as db:
        db.add_all(
            Asset(symbol=f"T-{t.name}", name=f"fresh {t.name}", type=t, currency="USD")
            for t in AssetType
        )
        await db.commit()
        stored = (await db.execute(select(Asset).order_by(Asset.symbol))).scalars().all()
    assert {a.type for a in stored} == set(AssetType)
    await engine.dispose()

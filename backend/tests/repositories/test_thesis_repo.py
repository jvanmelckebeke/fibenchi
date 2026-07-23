"""Tests for the global ThesisRepository — CRUD against a real SQLite DB."""

from datetime import date

import pytest

from app.repositories.thesis_repo import ThesisRepository

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_create_and_get_by_id(db):
    repo = ThesisRepository(db)
    created = await repo.create(
        name="El Niño", color="#22c55e", description="advisories",
        status="watching", opened_at=date(2026, 3, 1),
    )
    assert created.id is not None

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.name == "El Niño"
    assert fetched.status == "watching"
    assert fetched.opened_at == date(2026, 3, 1)
    assert fetched.assets == []


async def test_get_by_name(db):
    repo = ThesisRepository(db)
    await repo.create(
        name="Cables", color="#3b82f6", description=None,
        status="live", opened_at=date(2026, 1, 1),
    )
    found = await repo.get_by_name("Cables")
    assert found is not None
    assert found.name == "Cables"
    assert await repo.get_by_name("Nope") is None


async def test_list_all_ordered_by_name(db):
    repo = ThesisRepository(db)
    for name in ("Zinc", "Aluminium", "Copper"):
        await repo.create(
            name=name, color="#3b82f6", description=None,
            status="watching", opened_at=date(2026, 1, 1),
        )
    names = [t.name for t in await repo.list_all()]
    assert names == sorted(names)


async def test_delete(db):
    repo = ThesisRepository(db)
    created = await repo.create(
        name="Temp", color="#3b82f6", description=None,
        status="watching", opened_at=date(2026, 1, 1),
    )
    await repo.delete(created)
    assert await repo.get_by_id(created.id) is None

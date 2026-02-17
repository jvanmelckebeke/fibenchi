"""Tests for TagRepository — query methods against real SQLite DB."""

import pytest

from app.models import Tag
from app.repositories.tag_repo import TagRepository

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_list_all_returns_tags_ordered_by_name(db):
    repo = TagRepository(db)
    await repo.create(name="value", color="#22c55e")
    await repo.create(name="growth", color="#3b82f6")
    await repo.create(name="momentum", color="#ef4444")

    result = await repo.list_all()
    names = [t.name for t in result]
    assert names == ["growth", "momentum", "value"]


async def test_list_all_returns_empty(db):
    repo = TagRepository(db)
    result = await repo.list_all()
    assert result == []


async def test_get_by_id_found(db):
    repo = TagRepository(db)
    created = await repo.create(name="dividend", color="#f59e0b")

    result = await repo.get_by_id(created.id)
    assert result is not None
    assert result.name == "dividend"
    assert result.color == "#f59e0b"


async def test_get_by_id_not_found(db):
    repo = TagRepository(db)
    result = await repo.get_by_id(9999)
    assert result is None


async def test_get_by_name_found(db):
    repo = TagRepository(db)
    await repo.create(name="blue-chip", color="#1e40af")

    result = await repo.get_by_name("blue-chip")
    assert result is not None
    assert result.name == "blue-chip"


async def test_get_by_name_not_found(db):
    repo = TagRepository(db)
    result = await repo.get_by_name("nonexistent")
    assert result is None


async def test_create_with_all_fields(db):
    repo = TagRepository(db)
    tag = await repo.create(name="speculative", color="#a855f7")

    assert tag.id is not None
    assert tag.name == "speculative"
    assert tag.color == "#a855f7"


async def test_save_updates_tag(db):
    repo = TagRepository(db)
    tag = await repo.create(name="tech", color="#3b82f6")

    tag.color = "#ef4444"
    saved = await repo.save(tag)

    assert saved.color == "#ef4444"

    fetched = await repo.get_by_id(tag.id)
    assert fetched.color == "#ef4444"


async def test_delete_removes_tag(db):
    repo = TagRepository(db)
    tag = await repo.create(name="remove-me", color="#000000")
    tag_id = tag.id

    await repo.delete(tag)

    result = await repo.get_by_id(tag_id)
    assert result is None

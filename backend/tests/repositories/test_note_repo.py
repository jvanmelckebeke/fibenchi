"""Tests for NoteRepository — query methods against real SQLite DB."""

import pytest

from app.models import Asset, AssetType, Note
from app.repositories.note_repo import NoteRepository
from tests.helpers import create_test_asset as _create_asset

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_get_by_asset_returns_none_when_not_found(db):
    asset = await _create_asset(db, "AAPL")
    repo = NoteRepository(db)

    result = await repo.get_by_asset(asset.id)
    assert result is None


async def test_get_by_asset_finds_existing(db):
    asset = await _create_asset(db, "AAPL")
    repo = NoteRepository(db)

    await repo.upsert(asset.id, "Strong moat and growing services revenue")

    result = await repo.get_by_asset(asset.id)
    assert result is not None
    assert result.asset_id == asset.id
    assert result.content == "Strong moat and growing services revenue"


async def test_upsert_creates_new_note(db):
    asset = await _create_asset(db, "AAPL")
    repo = NoteRepository(db)

    note = await repo.upsert(asset.id, "Initial note content")

    assert note.id is not None
    assert note.asset_id == asset.id
    assert note.content == "Initial note content"


async def test_upsert_updates_existing_note(db):
    asset = await _create_asset(db, "AAPL")
    repo = NoteRepository(db)

    original = await repo.upsert(asset.id, "Original content")
    original_id = original.id

    updated = await repo.upsert(asset.id, "Updated content")

    assert updated.id == original_id
    assert updated.content == "Updated content"

    fetched = await repo.get_by_asset(asset.id)
    assert fetched.content == "Updated content"

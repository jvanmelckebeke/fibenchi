"""Unit tests for note_service — tests service logic with mocked repos."""

import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.note import NoteResponse
from app.services.note_service import get_note, upsert_note

pytestmark = pytest.mark.asyncio(loop_scope="function")


@patch("app.services.note_service.NoteRepository")
async def test_get_note_returns_default_with_fallback_date_when_not_found(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.get_by_asset = AsyncMock(return_value=None)
    fallback = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)

    result = await get_note(db, asset_id=42, fallback_date=fallback)

    MockRepo.assert_called_once_with(db)
    mock_repo.get_by_asset.assert_awaited_once_with(42)
    assert isinstance(result, NoteResponse)
    assert result.content == ""
    assert result.updated_at == fallback


@patch("app.services.note_service.NoteRepository")
async def test_get_note_returns_note_when_found(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    note = MagicMock()
    note.content = "Buy and hold long-term"
    note.updated_at = datetime.datetime(2025, 6, 15, tzinfo=datetime.timezone.utc)
    mock_repo.get_by_asset = AsyncMock(return_value=note)
    fallback = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)

    result = await get_note(db, asset_id=42, fallback_date=fallback)

    assert result == note


@patch("app.services.note_service.NoteRepository")
async def test_upsert_note_delegates_to_repo(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    updated_note = MagicMock()
    mock_repo.upsert = AsyncMock(return_value=updated_note)

    result = await upsert_note(db, asset_id=42, content="Updated note")

    MockRepo.assert_called_once_with(db)
    mock_repo.upsert.assert_awaited_once_with(42, "Updated note")
    assert result == updated_note

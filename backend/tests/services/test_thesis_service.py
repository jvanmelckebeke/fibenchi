"""Unit tests for thesis_service — tests service logic with mocked repos."""

import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.thesis import ThesisResponse
from app.services.thesis_service import get_thesis, upsert_thesis

pytestmark = pytest.mark.asyncio(loop_scope="function")


@patch("app.services.thesis_service.ThesisRepository")
async def test_get_thesis_returns_default_with_fallback_date_when_not_found(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.get_by_asset = AsyncMock(return_value=None)
    fallback = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)

    result = await get_thesis(db, asset_id=42, fallback_date=fallback)

    MockRepo.assert_called_once_with(db)
    mock_repo.get_by_asset.assert_awaited_once_with(42)
    assert isinstance(result, ThesisResponse)
    assert result.content == ""
    assert result.updated_at == fallback


@patch("app.services.thesis_service.ThesisRepository")
async def test_get_thesis_returns_thesis_when_found(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    thesis = MagicMock()
    thesis.content = "Buy and hold long-term"
    thesis.updated_at = datetime.datetime(2025, 6, 15, tzinfo=datetime.timezone.utc)
    mock_repo.get_by_asset = AsyncMock(return_value=thesis)
    fallback = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)

    result = await get_thesis(db, asset_id=42, fallback_date=fallback)

    assert result == thesis


@patch("app.services.thesis_service.ThesisRepository")
async def test_upsert_thesis_delegates_to_repo(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    updated_thesis = MagicMock()
    mock_repo.upsert = AsyncMock(return_value=updated_thesis)

    result = await upsert_thesis(db, asset_id=42, content="Updated thesis")

    MockRepo.assert_called_once_with(db)
    mock_repo.upsert.assert_awaited_once_with(42, "Updated thesis")
    assert result == updated_thesis

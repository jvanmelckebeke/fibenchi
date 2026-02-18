"""Unit tests for settings_service — tests service logic with mocked repos."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.settings import SettingsResponse
from app.services.settings_service import get_settings, update_settings

pytestmark = pytest.mark.asyncio(loop_scope="function")


@patch("app.services.settings_service.SettingsRepository")
async def test_get_settings_returns_default_when_no_row(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.get = AsyncMock(return_value=None)

    result = await get_settings(db)

    MockRepo.assert_called_once_with(db)
    mock_repo.get.assert_awaited_once()
    assert isinstance(result, SettingsResponse)
    assert result.data == {}


@patch("app.services.settings_service.SettingsRepository")
async def test_get_settings_returns_row_when_found(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    row = MagicMock()
    row.data = {"compact_mode": True, "group_show_rsi": False}
    mock_repo.get = AsyncMock(return_value=row)

    result = await get_settings(db)

    assert result == row


@patch("app.services.settings_service.SettingsRepository")
async def test_update_settings_delegates_to_repo(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    updated_row = MagicMock()
    mock_repo.upsert = AsyncMock(return_value=updated_row)
    data = {"compact_mode": True}

    result = await update_settings(db, data)

    MockRepo.assert_called_once_with(db)
    mock_repo.upsert.assert_awaited_once_with(data)
    assert result == updated_row

"""Tests for SettingsRepository — query methods against real SQLite DB."""

import pytest

from app.models.user_settings import UserSettings
from app.repositories.settings_repo import SettingsRepository

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_get_returns_none_when_empty(db):
    repo = SettingsRepository(db)
    result = await repo.get()
    assert result is None


async def test_upsert_creates_new_settings(db):
    repo = SettingsRepository(db)
    settings = await repo.upsert({"theme": "dark", "currency": "EUR"})

    assert settings.id == 1
    assert settings.data == {"theme": "dark", "currency": "EUR"}


async def test_upsert_updates_existing_settings(db):
    repo = SettingsRepository(db)
    await repo.upsert({"theme": "dark"})

    updated = await repo.upsert({"theme": "light", "language": "en"})

    assert updated.id == 1
    assert updated.data == {"theme": "light", "language": "en"}


async def test_get_retrieves_after_upsert(db):
    repo = SettingsRepository(db)
    await repo.upsert({"refresh_interval": 300, "notifications": True})

    result = await repo.get()
    assert result is not None
    assert result.id == 1
    assert result.data["refresh_interval"] == 300
    assert result.data["notifications"] is True

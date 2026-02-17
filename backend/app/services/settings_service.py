from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.settings_repo import SettingsRepository
from app.schemas.settings import SettingsResponse


async def get_settings(db: AsyncSession) -> SettingsResponse:
    row = await SettingsRepository(db).get()
    if not row:
        return SettingsResponse(data={})
    return row


async def update_settings(db: AsyncSession, data: dict):
    return await SettingsRepository(db).upsert(data)

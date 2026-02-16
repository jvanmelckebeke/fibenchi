from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_settings import UserSettings


class SettingsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self) -> UserSettings | None:
        result = await self.db.execute(
            select(UserSettings).where(UserSettings.id == 1)
        )
        return result.scalar_one_or_none()

    async def upsert(self, data: dict) -> UserSettings:
        row = await self.get()
        if row:
            row.data = data
        else:
            row = UserSettings(id=1, data=data)
            self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

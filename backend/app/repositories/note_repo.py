from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Note


class NoteRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_asset(self, asset_id: int) -> Note | None:
        result = await self.db.execute(
            select(Note).where(Note.asset_id == asset_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, asset_id: int, content: str) -> Note:
        note = await self.get_by_asset(asset_id)
        if note:
            note.content = content
        else:
            note = Note(asset_id=asset_id, content=content)
            self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)
        return note

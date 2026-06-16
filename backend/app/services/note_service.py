from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.note_repo import NoteRepository
from app.schemas.note import NoteResponse


async def get_note(db: AsyncSession, asset_id: int, fallback_date) -> NoteResponse:
    note = await NoteRepository(db).get_by_asset(asset_id)
    if not note:
        return NoteResponse(content="", updated_at=fallback_date)
    return note


async def upsert_note(db: AsyncSession, asset_id: int, content: str):
    return await NoteRepository(db).upsert(asset_id, content)

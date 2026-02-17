from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.thesis_repo import ThesisRepository
from app.schemas.thesis import ThesisResponse


async def get_thesis(db: AsyncSession, asset_id: int, fallback_date) -> ThesisResponse:
    thesis = await ThesisRepository(db).get_by_asset(asset_id)
    if not thesis:
        return ThesisResponse(content="", updated_at=fallback_date)
    return thesis


async def upsert_thesis(db: AsyncSession, asset_id: int, content: str):
    return await ThesisRepository(db).upsert(asset_id, content)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Thesis


class ThesisRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_asset(self, asset_id: int) -> Thesis | None:
        result = await self.db.execute(
            select(Thesis).where(Thesis.asset_id == asset_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, asset_id: int, content: str) -> Thesis:
        thesis = await self.get_by_asset(asset_id)
        if thesis:
            thesis.content = content
        else:
            thesis = Thesis(asset_id=asset_id, content=content)
            self.db.add(thesis)
        await self.db.commit()
        await self.db.refresh(thesis)
        return thesis

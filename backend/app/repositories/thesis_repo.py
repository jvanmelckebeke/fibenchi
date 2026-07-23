from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Thesis


class ThesisRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> list[Thesis]:
        result = await self.db.execute(
            select(Thesis).options(selectinload(Thesis.assets)).order_by(Thesis.name)
        )
        return list(result.scalars().all())

    async def get_by_id(self, thesis_id: int) -> Thesis | None:
        result = await self.db.execute(
            select(Thesis).options(selectinload(Thesis.assets)).where(Thesis.id == thesis_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Thesis | None:
        result = await self.db.execute(select(Thesis).where(Thesis.name == name))
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Thesis:
        thesis = Thesis(**kwargs)
        self.db.add(thesis)
        await self.db.commit()
        await self.db.refresh(thesis)
        return thesis

    async def save(self, thesis: Thesis) -> Thesis:
        await self.db.commit()
        await self.db.refresh(thesis)
        return thesis

    async def delete(self, thesis: Thesis) -> None:
        await self.db.delete(thesis)
        await self.db.commit()

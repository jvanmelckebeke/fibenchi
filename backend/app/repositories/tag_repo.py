from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Asset, Tag


class TagRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> list[Tag]:
        result = await self.db.execute(
            select(Tag)
            .options(selectinload(Tag.assets).selectinload(Asset.tags))
            .order_by(Tag.name)
        )
        return list(result.scalars().all())

    async def get_by_id(self, tag_id: int) -> Tag | None:
        result = await self.db.execute(select(Tag).where(Tag.id == tag_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Tag | None:
        result = await self.db.execute(select(Tag).where(Tag.name == name))
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Tag:
        tag = Tag(**kwargs)
        self.db.add(tag)
        await self.db.commit()
        await self.db.refresh(tag)
        return tag

    async def save(self, tag: Tag) -> Tag:
        await self.db.commit()
        await self.db.refresh(tag)
        return tag

    async def delete(self, tag: Tag) -> None:
        await self.db.delete(tag)
        await self.db.commit()

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Annotation


class AnnotationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_asset(self, asset_id: int) -> list[Annotation]:
        result = await self.db.execute(
            select(Annotation)
            .where(Annotation.asset_id == asset_id)
            .order_by(Annotation.date)
        )
        return list(result.scalars().all())

    async def get_by_id_and_asset(self, annotation_id: int, asset_id: int) -> Annotation | None:
        result = await self.db.execute(
            select(Annotation).where(
                Annotation.id == annotation_id,
                Annotation.asset_id == asset_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Annotation:
        annotation = Annotation(**kwargs)
        self.db.add(annotation)
        await self.db.commit()
        await self.db.refresh(annotation)
        return annotation

    async def delete(self, annotation: Annotation) -> None:
        await self.db.delete(annotation)
        await self.db.commit()

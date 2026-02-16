from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pseudo_etf import PseudoETF, PseudoEtfAnnotation, PseudoEtfThesis


class PseudoEtfRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Core CRUD ---

    async def list_all(self) -> list[PseudoETF]:
        result = await self.db.execute(select(PseudoETF).order_by(PseudoETF.name))
        return list(result.scalars().all())

    async def get_by_id(self, etf_id: int) -> PseudoETF | None:
        return await self.db.get(PseudoETF, etf_id)

    async def get_by_name(self, name: str) -> PseudoETF | None:
        result = await self.db.execute(
            select(PseudoETF).where(PseudoETF.name == name)
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> PseudoETF:
        etf = PseudoETF(**kwargs)
        self.db.add(etf)
        await self.db.commit()
        await self.db.refresh(etf)
        return etf

    async def save(self, etf: PseudoETF) -> PseudoETF:
        await self.db.commit()
        await self.db.refresh(etf)
        return etf

    async def delete(self, etf: PseudoETF) -> None:
        await self.db.delete(etf)
        await self.db.commit()

    # --- Thesis ---

    async def get_thesis(self, etf_id: int) -> PseudoEtfThesis | None:
        result = await self.db.execute(
            select(PseudoEtfThesis).where(PseudoEtfThesis.pseudo_etf_id == etf_id)
        )
        return result.scalar_one_or_none()

    async def upsert_thesis(self, etf_id: int, content: str) -> PseudoEtfThesis:
        thesis = await self.get_thesis(etf_id)
        if thesis:
            thesis.content = content
        else:
            thesis = PseudoEtfThesis(pseudo_etf_id=etf_id, content=content)
            self.db.add(thesis)
        await self.db.commit()
        await self.db.refresh(thesis)
        return thesis

    # --- Annotations ---

    async def list_annotations(self, etf_id: int) -> list[PseudoEtfAnnotation]:
        result = await self.db.execute(
            select(PseudoEtfAnnotation)
            .where(PseudoEtfAnnotation.pseudo_etf_id == etf_id)
            .order_by(PseudoEtfAnnotation.date)
        )
        return list(result.scalars().all())

    async def create_annotation(self, **kwargs) -> PseudoEtfAnnotation:
        annotation = PseudoEtfAnnotation(**kwargs)
        self.db.add(annotation)
        await self.db.commit()
        await self.db.refresh(annotation)
        return annotation

    async def get_annotation(self, annotation_id: int, etf_id: int) -> PseudoEtfAnnotation | None:
        result = await self.db.execute(
            select(PseudoEtfAnnotation).where(
                PseudoEtfAnnotation.id == annotation_id,
                PseudoEtfAnnotation.pseudo_etf_id == etf_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_annotation(self, annotation: PseudoEtfAnnotation) -> None:
        await self.db.delete(annotation)
        await self.db.commit()

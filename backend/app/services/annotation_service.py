from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.annotation_repo import AnnotationRepository


async def list_annotations(db: AsyncSession, asset_id: int):
    return await AnnotationRepository(db).list_by_asset(asset_id)


async def create_annotation(db: AsyncSession, asset_id: int, **kwargs):
    return await AnnotationRepository(db).create(asset_id=asset_id, **kwargs)


async def delete_annotation(db: AsyncSession, annotation_id: int, asset_id: int):
    repo = AnnotationRepository(db)
    annotation = await repo.get_by_id_and_asset(annotation_id, asset_id)
    if not annotation:
        raise HTTPException(404, "Annotation not found")
    await repo.delete(annotation)

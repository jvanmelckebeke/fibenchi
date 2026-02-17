from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.lookups import get_asset
from app.schemas.annotation import AnnotationCreate, AnnotationResponse
from app.services import annotation_service

router = APIRouter(prefix="/api/assets/{symbol}/annotations", tags=["annotations"])


@router.get("", response_model=list[AnnotationResponse], summary="List chart annotations for an asset")
async def list_annotations(symbol: str, db: AsyncSession = Depends(get_db)):
    asset = await get_asset(symbol, db)
    return await annotation_service.list_annotations(db, asset.id)


@router.post("", response_model=AnnotationResponse, status_code=201, summary="Create a chart annotation")
async def create_annotation(symbol: str, data: AnnotationCreate, db: AsyncSession = Depends(get_db)):
    asset = await get_asset(symbol, db)
    return await annotation_service.create_annotation(
        db, asset.id, date=data.date, title=data.title, body=data.body, color=data.color,
    )


@router.delete("/{annotation_id}", status_code=204, summary="Delete a chart annotation")
async def delete_annotation(symbol: str, annotation_id: int, db: AsyncSession = Depends(get_db)):
    asset = await get_asset(symbol, db)
    await annotation_service.delete_annotation(db, annotation_id, asset.id)

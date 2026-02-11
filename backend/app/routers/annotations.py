from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Annotation, Asset
from app.schemas.annotation import AnnotationCreate, AnnotationResponse

router = APIRouter(prefix="/api/assets/{symbol}/annotations", tags=["annotations"])


@router.get("", response_model=list[AnnotationResponse], summary="List chart annotations for an asset")
async def list_annotations(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")

    result = await db.execute(
        select(Annotation)
        .where(Annotation.asset_id == asset.id)
        .order_by(Annotation.date)
    )
    return result.scalars().all()


@router.post("", response_model=AnnotationResponse, status_code=201, summary="Create a chart annotation")
async def create_annotation(symbol: str, data: AnnotationCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")

    annotation = Annotation(
        asset_id=asset.id,
        date=data.date,
        title=data.title,
        body=data.body,
        color=data.color,
    )
    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)
    return annotation


@router.delete("/{annotation_id}", status_code=204, summary="Delete a chart annotation")
async def delete_annotation(symbol: str, annotation_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")

    result = await db.execute(
        select(Annotation).where(Annotation.id == annotation_id, Annotation.asset_id == asset.id)
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(404, "Annotation not found")

    await db.delete(annotation)
    await db.commit()

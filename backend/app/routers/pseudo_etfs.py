from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pseudo_etf import PseudoETF, PseudoEtfAnnotation, PseudoEtfThesis
from app.models.asset import Asset
from app.schemas.pseudo_etf import (
    PseudoETFCreate,
    PseudoETFUpdate,
    PseudoETFAddConstituents,
    PseudoETFResponse,
)
from app.schemas.thesis import ThesisResponse, ThesisUpdate
from app.schemas.annotation import AnnotationCreate, AnnotationResponse

router = APIRouter(prefix="/api/pseudo-etfs", tags=["pseudo-etfs"])


@router.get("", response_model=list[PseudoETFResponse], summary="List all pseudo-ETFs")
async def list_pseudo_etfs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PseudoETF).order_by(PseudoETF.name))
    return result.scalars().all()


@router.post("", response_model=PseudoETFResponse, status_code=201, summary="Create a pseudo-ETF basket")
async def create_pseudo_etf(data: PseudoETFCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(PseudoETF).where(PseudoETF.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Pseudo-ETF with this name already exists")

    etf = PseudoETF(
        name=data.name,
        description=data.description,
        base_date=data.base_date,
        base_value=data.base_value,
    )
    db.add(etf)
    await db.commit()
    await db.refresh(etf)
    return etf


@router.get("/{etf_id}", response_model=PseudoETFResponse, summary="Get a pseudo-ETF by ID")
async def get_pseudo_etf(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")
    return etf


@router.put("/{etf_id}", response_model=PseudoETFResponse, summary="Update a pseudo-ETF")
async def update_pseudo_etf(etf_id: int, data: PseudoETFUpdate, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(etf, field, value)

    await db.commit()
    await db.refresh(etf)
    return etf


@router.delete("/{etf_id}", status_code=204, summary="Delete a pseudo-ETF")
async def delete_pseudo_etf(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")
    await db.delete(etf)
    await db.commit()


@router.post("/{etf_id}/constituents", response_model=PseudoETFResponse, summary="Add constituent assets to a pseudo-ETF")
async def add_constituents(
    etf_id: int, data: PseudoETFAddConstituents, db: AsyncSession = Depends(get_db)
):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    result = await db.execute(select(Asset).where(Asset.id.in_(data.asset_ids)))
    assets = result.scalars().all()

    existing_ids = {a.id for a in etf.constituents}
    for asset in assets:
        if asset.id not in existing_ids:
            etf.constituents.append(asset)

    await db.commit()
    await db.refresh(etf)
    return etf


@router.delete("/{etf_id}/constituents/{asset_id}", response_model=PseudoETFResponse, summary="Remove a constituent from a pseudo-ETF")
async def remove_constituent(
    etf_id: int, asset_id: int, db: AsyncSession = Depends(get_db)
):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    asset = next((a for a in etf.constituents if a.id == asset_id), None)
    if not asset:
        raise HTTPException(404, "Asset not in this pseudo-ETF")

    etf.constituents.remove(asset)
    await db.commit()
    await db.refresh(etf)
    return etf


# --- Thesis ---

@router.get("/{etf_id}/thesis", response_model=ThesisResponse, summary="Get pseudo-ETF investment thesis")
async def get_etf_thesis(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    result = await db.execute(select(PseudoEtfThesis).where(PseudoEtfThesis.pseudo_etf_id == etf_id))
    thesis = result.scalar_one_or_none()
    if not thesis:
        return ThesisResponse(content="", updated_at=etf.created_at)
    return thesis


@router.put("/{etf_id}/thesis", response_model=ThesisResponse, summary="Create or update pseudo-ETF thesis")
async def update_etf_thesis(etf_id: int, data: ThesisUpdate, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    result = await db.execute(select(PseudoEtfThesis).where(PseudoEtfThesis.pseudo_etf_id == etf_id))
    thesis = result.scalar_one_or_none()

    if thesis:
        thesis.content = data.content
    else:
        thesis = PseudoEtfThesis(pseudo_etf_id=etf_id, content=data.content)
        db.add(thesis)

    await db.commit()
    await db.refresh(thesis)
    return thesis


# --- Annotations ---

@router.get("/{etf_id}/annotations", response_model=list[AnnotationResponse], summary="List pseudo-ETF chart annotations")
async def list_etf_annotations(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    result = await db.execute(
        select(PseudoEtfAnnotation)
        .where(PseudoEtfAnnotation.pseudo_etf_id == etf_id)
        .order_by(PseudoEtfAnnotation.date)
    )
    return result.scalars().all()


@router.post("/{etf_id}/annotations", response_model=AnnotationResponse, status_code=201, summary="Create a pseudo-ETF chart annotation")
async def create_etf_annotation(etf_id: int, data: AnnotationCreate, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    annotation = PseudoEtfAnnotation(
        pseudo_etf_id=etf_id,
        date=data.date,
        title=data.title,
        body=data.body,
        color=data.color,
    )
    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)
    return annotation


@router.delete("/{etf_id}/annotations/{annotation_id}", status_code=204, summary="Delete a pseudo-ETF chart annotation")
async def delete_etf_annotation(etf_id: int, annotation_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    result = await db.execute(
        select(PseudoEtfAnnotation).where(
            PseudoEtfAnnotation.id == annotation_id,
            PseudoEtfAnnotation.pseudo_etf_id == etf_id,
        )
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(404, "Annotation not found")

    await db.delete(annotation)
    await db.commit()

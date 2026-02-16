from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.pseudo_etf import (
    PseudoETFCreate,
    PseudoETFUpdate,
    PseudoETFAddConstituents,
    PseudoETFResponse,
)
from app.schemas.thesis import ThesisResponse, ThesisUpdate
from app.schemas.annotation import AnnotationCreate, AnnotationResponse
from app.services import pseudo_etf_service

router = APIRouter(prefix="/api/pseudo-etfs", tags=["pseudo-etfs"])


@router.get("", response_model=list[PseudoETFResponse], summary="List all pseudo-ETFs")
async def list_pseudo_etfs(db: AsyncSession = Depends(get_db)):
    return await pseudo_etf_service.list_pseudo_etfs(db)


@router.post("", response_model=PseudoETFResponse, status_code=201, summary="Create a pseudo-ETF basket")
async def create_pseudo_etf(data: PseudoETFCreate, db: AsyncSession = Depends(get_db)):
    return await pseudo_etf_service.create_pseudo_etf(
        db, name=data.name, description=data.description,
        base_date=data.base_date, base_value=data.base_value,
    )


@router.get("/{etf_id}", response_model=PseudoETFResponse, summary="Get a pseudo-ETF by ID")
async def get_pseudo_etf_detail(etf_id: int, db: AsyncSession = Depends(get_db)):
    return await pseudo_etf_service.get_pseudo_etf_detail(db, etf_id)


@router.put("/{etf_id}", response_model=PseudoETFResponse, summary="Update a pseudo-ETF")
async def update_pseudo_etf(etf_id: int, data: PseudoETFUpdate, db: AsyncSession = Depends(get_db)):
    return await pseudo_etf_service.update_pseudo_etf(db, etf_id, data.model_dump(exclude_unset=True))


@router.delete("/{etf_id}", status_code=204, summary="Delete a pseudo-ETF")
async def delete_pseudo_etf(etf_id: int, db: AsyncSession = Depends(get_db)):
    await pseudo_etf_service.delete_pseudo_etf(db, etf_id)


@router.post("/{etf_id}/constituents", response_model=PseudoETFResponse, summary="Add constituent assets to a pseudo-ETF")
async def add_constituents(
    etf_id: int, data: PseudoETFAddConstituents, db: AsyncSession = Depends(get_db)
):
    return await pseudo_etf_service.add_constituents(db, etf_id, data.asset_ids)


@router.delete("/{etf_id}/constituents/{asset_id}", response_model=PseudoETFResponse, summary="Remove a constituent from a pseudo-ETF")
async def remove_constituent(
    etf_id: int, asset_id: int, db: AsyncSession = Depends(get_db)
):
    return await pseudo_etf_service.remove_constituent(db, etf_id, asset_id)


# --- Thesis ---

@router.get("/{etf_id}/thesis", response_model=ThesisResponse, summary="Get pseudo-ETF investment thesis")
async def get_etf_thesis(etf_id: int, db: AsyncSession = Depends(get_db)):
    return await pseudo_etf_service.get_thesis(db, etf_id)


@router.put("/{etf_id}/thesis", response_model=ThesisResponse, summary="Create or update pseudo-ETF thesis")
async def update_etf_thesis(etf_id: int, data: ThesisUpdate, db: AsyncSession = Depends(get_db)):
    return await pseudo_etf_service.upsert_thesis(db, etf_id, data.content)


# --- Annotations ---

@router.get("/{etf_id}/annotations", response_model=list[AnnotationResponse], summary="List pseudo-ETF chart annotations")
async def list_etf_annotations(etf_id: int, db: AsyncSession = Depends(get_db)):
    return await pseudo_etf_service.list_annotations(db, etf_id)


@router.post("/{etf_id}/annotations", response_model=AnnotationResponse, status_code=201, summary="Create a pseudo-ETF chart annotation")
async def create_etf_annotation(etf_id: int, data: AnnotationCreate, db: AsyncSession = Depends(get_db)):
    return await pseudo_etf_service.create_annotation(
        db, etf_id, date=data.date, title=data.title, body=data.body, color=data.color,
    )


@router.delete("/{etf_id}/annotations/{annotation_id}", status_code=204, summary="Delete a pseudo-ETF chart annotation")
async def delete_etf_annotation(etf_id: int, annotation_id: int, db: AsyncSession = Depends(get_db)):
    await pseudo_etf_service.delete_annotation(db, etf_id, annotation_id)

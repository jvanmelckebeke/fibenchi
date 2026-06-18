from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.thesis import (
    ThesisAddAssets,
    ThesisCreate,
    ThesisResponse,
    ThesisUpdate,
)
from app.services import thesis_service

router = APIRouter(prefix="/api/theses", tags=["theses"])


@router.get("", response_model=list[ThesisResponse], summary="List all theses")
async def list_theses(db: AsyncSession = Depends(get_db)):
    return await thesis_service.list_theses(db)


@router.post("", response_model=ThesisResponse, status_code=201, summary="Create a thesis")
async def create_thesis(data: ThesisCreate, db: AsyncSession = Depends(get_db)):
    return await thesis_service.create_thesis(
        db,
        name=data.name,
        color=data.color,
        icon=data.icon,
        description=data.description,
        status=data.status,
        opened_at=data.opened_at,
    )


@router.get("/{thesis_id}", response_model=ThesisResponse, summary="Get a thesis by ID")
async def get_thesis(thesis_id: int, db: AsyncSession = Depends(get_db)):
    return await thesis_service.get_thesis_detail(db, thesis_id)


@router.put("/{thesis_id}", response_model=ThesisResponse, summary="Update a thesis")
async def update_thesis(thesis_id: int, data: ThesisUpdate, db: AsyncSession = Depends(get_db)):
    return await thesis_service.update_thesis(db, thesis_id, data.model_dump(exclude_unset=True))


@router.delete("/{thesis_id}", status_code=204, summary="Delete a thesis")
async def delete_thesis(thesis_id: int, db: AsyncSession = Depends(get_db)):
    await thesis_service.delete_thesis(db, thesis_id)


@router.post("/{thesis_id}/assets", response_model=ThesisResponse, summary="Add member assets to a thesis")
async def add_assets(thesis_id: int, data: ThesisAddAssets, db: AsyncSession = Depends(get_db)):
    return await thesis_service.add_assets(db, thesis_id, data.asset_ids)


@router.delete("/{thesis_id}/assets/{asset_id}", response_model=ThesisResponse, summary="Remove a member asset from a thesis")
async def remove_asset(thesis_id: int, asset_id: int, db: AsyncSession = Depends(get_db)):
    return await thesis_service.remove_asset(db, thesis_id, asset_id)

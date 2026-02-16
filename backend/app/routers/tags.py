from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.asset import TagBrief
from app.schemas.tag import TagCreate, TagResponse, TagUpdate
from app.services import tag_service

router = APIRouter(prefix="/api/tags", tags=["tags"])
asset_tag_router = APIRouter(prefix="/api/assets", tags=["tags"])


@router.get("", response_model=list[TagResponse], summary="List all tags")
async def list_tags(db: AsyncSession = Depends(get_db)):
    return await tag_service.list_tags(db)


@router.post("", response_model=TagResponse, status_code=201, summary="Create a tag")
async def create_tag(data: TagCreate, db: AsyncSession = Depends(get_db)):
    return await tag_service.create_tag(db, data.name, data.color)


@router.put("/{tag_id}", response_model=TagResponse, summary="Update a tag")
async def update_tag(tag_id: int, data: TagUpdate, db: AsyncSession = Depends(get_db)):
    return await tag_service.update_tag(db, tag_id, data.name, data.color)


@router.delete("/{tag_id}", status_code=204, summary="Delete a tag")
async def delete_tag(tag_id: int, db: AsyncSession = Depends(get_db)):
    await tag_service.delete_tag(db, tag_id)


@asset_tag_router.post("/{symbol}/tags/{tag_id}", response_model=list[TagBrief], summary="Attach a tag to an asset")
async def attach_tag(symbol: str, tag_id: int, db: AsyncSession = Depends(get_db)):
    return await tag_service.attach_tag(db, symbol, tag_id)


@asset_tag_router.delete("/{symbol}/tags/{tag_id}", response_model=list[TagBrief], summary="Detach a tag from an asset")
async def detach_tag(symbol: str, tag_id: int, db: AsyncSession = Depends(get_db)):
    return await tag_service.detach_tag(db, symbol, tag_id)

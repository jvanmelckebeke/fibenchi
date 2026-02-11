from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Asset, Tag
from app.schemas.asset import TagBrief
from app.schemas.tag import TagCreate, TagResponse, TagUpdate

router = APIRouter(prefix="/api/tags", tags=["tags"])
asset_tag_router = APIRouter(prefix="/api/assets", tags=["tags"])


@router.get("", response_model=list[TagResponse], summary="List all tags")
async def list_tags(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tag).order_by(Tag.name))
    return result.scalars().all()


@router.post("", response_model=TagResponse, status_code=201, summary="Create a tag")
async def create_tag(data: TagCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Tag).where(Tag.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Tag '{data.name}' already exists")

    tag = Tag(name=data.name, color=data.color)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


@router.put("/{tag_id}", response_model=TagResponse, summary="Update a tag")
async def update_tag(tag_id: int, data: TagUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(404, "Tag not found")

    if data.name is not None:
        tag.name = data.name
    if data.color is not None:
        tag.color = data.color

    await db.commit()
    await db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=204, summary="Delete a tag")
async def delete_tag(tag_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(404, "Tag not found")
    await db.delete(tag)
    await db.commit()


@asset_tag_router.post("/{symbol}/tags/{tag_id}", response_model=list[TagBrief], summary="Attach a tag to an asset")
async def attach_tag(symbol: str, tag_id: int, db: AsyncSession = Depends(get_db)):
    asset_result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")

    tag_result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = tag_result.scalar_one_or_none()
    if not tag:
        raise HTTPException(404, "Tag not found")

    if tag not in asset.tags:
        asset.tags.append(tag)
        await db.commit()
        await db.refresh(asset)

    return asset.tags


@asset_tag_router.delete("/{symbol}/tags/{tag_id}", response_model=list[TagBrief], summary="Detach a tag from an asset")
async def detach_tag(symbol: str, tag_id: int, db: AsyncSession = Depends(get_db)):
    asset_result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")

    asset.tags = [t for t in asset.tags if t.id != tag_id]
    await db.commit()
    await db.refresh(asset)

    return asset.tags

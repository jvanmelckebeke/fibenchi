from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.asset_repo import AssetRepository
from app.repositories.tag_repo import TagRepository


async def list_tags(db: AsyncSession):
    return await TagRepository(db).list_all()


async def create_tag(db: AsyncSession, name: str, color: str):
    repo = TagRepository(db)
    if await repo.get_by_name(name):
        raise HTTPException(400, f"Tag '{name}' already exists")
    return await repo.create(name=name, color=color)


async def update_tag(db: AsyncSession, tag_id: int, name: str | None, color: str | None):
    repo = TagRepository(db)
    tag = await repo.get_by_id(tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if name is not None:
        tag.name = name
    if color is not None:
        tag.color = color
    return await repo.save(tag)


async def delete_tag(db: AsyncSession, tag_id: int):
    repo = TagRepository(db)
    tag = await repo.get_by_id(tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    await repo.delete(tag)


async def attach_tag(db: AsyncSession, symbol: str, tag_id: int):
    from app.routers.deps import get_asset
    asset = await get_asset(symbol, db)
    tag = await TagRepository(db).get_by_id(tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if tag not in asset.tags:
        asset.tags.append(tag)
        await AssetRepository(db).save(asset)
    return asset.tags


async def detach_tag(db: AsyncSession, symbol: str, tag_id: int):
    from app.routers.deps import get_asset
    asset = await get_asset(symbol, db)
    asset.tags = [t for t in asset.tags if t.id != tag_id]
    await AssetRepository(db).save(asset)
    return asset.tags

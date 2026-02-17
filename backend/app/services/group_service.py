from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.asset_repo import AssetRepository
from app.repositories.group_repo import GroupRepository
from app.services.entity_lookups import get_group


async def list_groups(db: AsyncSession):
    return await GroupRepository(db).list_all()


async def create_group(db: AsyncSession, name: str, description: str | None):
    repo = GroupRepository(db)
    if await repo.get_by_name(name):
        raise HTTPException(400, f"Group '{name}' already exists")
    return await repo.create(name=name, description=description)


async def get_group_detail(db: AsyncSession, group_id: int):
    return await get_group(group_id, db)


async def update_group(db: AsyncSession, group_id: int, name: str | None, description: str | None):
    group = await get_group(group_id, db)
    if name is not None:
        group.name = name
    if description is not None:
        group.description = description
    return await GroupRepository(db).save(group)


async def delete_group(db: AsyncSession, group_id: int):
    group = await get_group(group_id, db)
    await GroupRepository(db).delete(group)


async def add_assets(db: AsyncSession, group_id: int, asset_ids: list[int]):
    group = await get_group(group_id, db)
    assets = await AssetRepository(db).get_by_ids(asset_ids)
    existing_ids = {a.id for a in group.assets}
    for asset in assets:
        if asset.id not in existing_ids:
            group.assets.append(asset)
    return await GroupRepository(db).save(group)


async def remove_asset(db: AsyncSession, group_id: int, asset_id: int):
    group = await get_group(group_id, db)
    group.assets = [a for a in group.assets if a.id != asset_id]
    return await GroupRepository(db).save(group)

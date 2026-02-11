from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Asset, Group
from app.schemas.group import GroupAddAssets, GroupCreate, GroupResponse, GroupUpdate

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("", response_model=list[GroupResponse], summary="List all groups")
async def list_groups(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).order_by(Group.name))
    return result.scalars().all()


@router.post("", response_model=GroupResponse, status_code=201, summary="Create a group")
async def create_group(data: GroupCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Group).where(Group.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Group '{data.name}' already exists")

    group = Group(name=data.name, description=data.description)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.get("/{group_id}", response_model=GroupResponse, summary="Get a group by ID")
async def get_group(group_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")
    return group


@router.put("/{group_id}", response_model=GroupResponse, summary="Update a group")
async def update_group(group_id: int, data: GroupUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")

    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description

    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=204, summary="Delete a group")
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")
    await db.delete(group)
    await db.commit()


@router.post("/{group_id}/assets", response_model=GroupResponse, summary="Add assets to a group")
async def add_assets_to_group(group_id: int, data: GroupAddAssets, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")

    assets_result = await db.execute(select(Asset).where(Asset.id.in_(data.asset_ids)))
    assets = assets_result.scalars().all()

    existing_ids = {a.id for a in group.assets}
    for asset in assets:
        if asset.id not in existing_ids:
            group.assets.append(asset)

    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/{group_id}/assets/{asset_id}", response_model=GroupResponse, summary="Remove an asset from a group")
async def remove_asset_from_group(group_id: int, asset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")

    group.assets = [a for a in group.assets if a.id != asset_id]
    await db.commit()
    await db.refresh(group)
    return group

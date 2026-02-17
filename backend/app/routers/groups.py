from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.group import GroupAddAssets, GroupCreate, GroupResponse, GroupUpdate
from app.services import group_service

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("", response_model=list[GroupResponse], summary="List all groups")
async def list_groups(db: AsyncSession = Depends(get_db)):
    return await group_service.list_groups(db)


@router.post("", response_model=GroupResponse, status_code=201, summary="Create a group")
async def create_group(data: GroupCreate, db: AsyncSession = Depends(get_db)):
    return await group_service.create_group(db, data.name, data.description)


@router.get("/{group_id}", response_model=GroupResponse, summary="Get a group by ID")
async def get_group_detail(group_id: int, db: AsyncSession = Depends(get_db)):
    return await group_service.get_group_detail(db, group_id)


@router.put("/{group_id}", response_model=GroupResponse, summary="Update a group")
async def update_group(group_id: int, data: GroupUpdate, db: AsyncSession = Depends(get_db)):
    return await group_service.update_group(db, group_id, data.name, data.description)


@router.delete("/{group_id}", status_code=204, summary="Delete a group")
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db)):
    await group_service.delete_group(db, group_id)


@router.post("/{group_id}/assets", response_model=GroupResponse, summary="Add assets to a group")
async def add_assets_to_group(group_id: int, data: GroupAddAssets, db: AsyncSession = Depends(get_db)):
    return await group_service.add_assets(db, group_id, data.asset_ids)


@router.delete("/{group_id}/assets/{asset_id}", response_model=GroupResponse, summary="Remove an asset from a group")
async def remove_asset_from_group(group_id: int, asset_id: int, db: AsyncSession = Depends(get_db)):
    return await group_service.remove_asset(db, group_id, asset_id)

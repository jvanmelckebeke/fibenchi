"""Global Thesis CRUD + membership business logic.

A thesis is a cross-cutting basket of tickers tracked under one hypothesis.
Membership is many-to-many (an asset can be in several theses).
"""

from datetime import date

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thesis import ThesisStatus
from app.repositories.asset_repo import AssetRepository
from app.repositories.thesis_repo import ThesisRepository
from app.services.entity_lookups import get_thesis


async def list_theses(db: AsyncSession):
    return await ThesisRepository(db).list_all()


async def get_thesis_detail(db: AsyncSession, thesis_id: int):
    return await get_thesis(thesis_id, db)


async def create_thesis(
    db: AsyncSession,
    name: str,
    color: str,
    description: str | None,
    status: ThesisStatus,
    opened_at: date | None,
):
    repo = ThesisRepository(db)
    if await repo.get_by_name(name):
        raise HTTPException(400, f"Thesis '{name}' already exists")
    return await repo.create(
        name=name,
        color=color,
        description=description,
        status=status.value,
        opened_at=opened_at or date.today(),
    )


async def update_thesis(db: AsyncSession, thesis_id: int, data: dict):
    thesis = await get_thesis(thesis_id, db)
    if "name" in data:
        thesis.name = data["name"]
    if "color" in data:
        thesis.color = data["color"]
    if "description" in data:
        thesis.description = data["description"]
    if data.get("status") is not None:
        status = data["status"]
        thesis.status = status.value if isinstance(status, ThesisStatus) else status
    if data.get("opened_at") is not None:
        thesis.opened_at = data["opened_at"]
    return await ThesisRepository(db).save(thesis)


async def delete_thesis(db: AsyncSession, thesis_id: int):
    thesis = await get_thesis(thesis_id, db)
    await ThesisRepository(db).delete(thesis)


async def add_assets(db: AsyncSession, thesis_id: int, asset_ids: list[int]):
    thesis = await get_thesis(thesis_id, db)
    assets = await AssetRepository(db).get_by_ids(asset_ids)
    existing_ids = {a.id for a in thesis.assets}
    for asset in assets:
        if asset.id not in existing_ids:
            thesis.assets.append(asset)
    return await ThesisRepository(db).save(thesis)


async def remove_asset(db: AsyncSession, thesis_id: int, asset_id: int):
    thesis = await get_thesis(thesis_id, db)
    thesis.assets = [a for a in thesis.assets if a.id != asset_id]
    return await ThesisRepository(db).save(thesis)

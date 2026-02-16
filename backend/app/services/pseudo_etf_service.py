"""Pseudo-ETF CRUD business logic."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.asset_repo import AssetRepository
from app.repositories.pseudo_etf_repo import PseudoEtfRepository
from app.schemas.thesis import ThesisResponse


async def list_pseudo_etfs(db: AsyncSession):
    return await PseudoEtfRepository(db).list_all()


async def create_pseudo_etf(db: AsyncSession, **kwargs):
    repo = PseudoEtfRepository(db)
    if await repo.get_by_name(kwargs["name"]):
        raise HTTPException(400, "Pseudo-ETF with this name already exists")
    return await repo.create(**kwargs)


async def get_pseudo_etf_detail(db: AsyncSession, etf_id: int):
    from app.routers.deps import get_pseudo_etf
    return await get_pseudo_etf(etf_id, db)


async def update_pseudo_etf(db: AsyncSession, etf_id: int, data: dict):
    from app.routers.deps import get_pseudo_etf
    etf = await get_pseudo_etf(etf_id, db)
    for field, value in data.items():
        setattr(etf, field, value)
    return await PseudoEtfRepository(db).save(etf)


async def delete_pseudo_etf(db: AsyncSession, etf_id: int):
    from app.routers.deps import get_pseudo_etf
    etf = await get_pseudo_etf(etf_id, db)
    await PseudoEtfRepository(db).delete(etf)


async def add_constituents(db: AsyncSession, etf_id: int, asset_ids: list[int]):
    from app.routers.deps import get_pseudo_etf
    etf = await get_pseudo_etf(etf_id, db)
    assets = await AssetRepository(db).get_by_ids(asset_ids)
    existing_ids = {a.id for a in etf.constituents}
    for asset in assets:
        if asset.id not in existing_ids:
            etf.constituents.append(asset)
    return await PseudoEtfRepository(db).save(etf)


async def remove_constituent(db: AsyncSession, etf_id: int, asset_id: int):
    from app.routers.deps import get_pseudo_etf
    etf = await get_pseudo_etf(etf_id, db)
    asset = next((a for a in etf.constituents if a.id == asset_id), None)
    if not asset:
        raise HTTPException(404, "Asset not in this pseudo-ETF")
    etf.constituents.remove(asset)
    return await PseudoEtfRepository(db).save(etf)


# --- Thesis ---

async def get_thesis(db: AsyncSession, etf_id: int):
    from app.routers.deps import get_pseudo_etf
    etf = await get_pseudo_etf(etf_id, db)
    thesis = await PseudoEtfRepository(db).get_thesis(etf_id)
    if not thesis:
        return ThesisResponse(content="", updated_at=etf.created_at)
    return thesis


async def upsert_thesis(db: AsyncSession, etf_id: int, content: str):
    from app.routers.deps import get_pseudo_etf
    await get_pseudo_etf(etf_id, db)
    return await PseudoEtfRepository(db).upsert_thesis(etf_id, content)


# --- Annotations ---

async def list_annotations(db: AsyncSession, etf_id: int):
    from app.routers.deps import get_pseudo_etf
    await get_pseudo_etf(etf_id, db)
    return await PseudoEtfRepository(db).list_annotations(etf_id)


async def create_annotation(db: AsyncSession, etf_id: int, **kwargs):
    from app.routers.deps import get_pseudo_etf
    await get_pseudo_etf(etf_id, db)
    return await PseudoEtfRepository(db).create_annotation(pseudo_etf_id=etf_id, **kwargs)


async def delete_annotation(db: AsyncSession, etf_id: int, annotation_id: int):
    from app.routers.deps import get_pseudo_etf
    await get_pseudo_etf(etf_id, db)
    repo = PseudoEtfRepository(db)
    annotation = await repo.get_annotation(annotation_id, etf_id)
    if not annotation:
        raise HTTPException(404, "Annotation not found")
    await repo.delete_annotation(annotation)

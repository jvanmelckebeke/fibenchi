"""Pseudo-ETF CRUD business logic."""

import logging

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.repositories.pseudo_etf_repo import PseudoEtfRepository
from app.schemas.thesis import ThesisResponse
from app.services.entity_lookups import get_pseudo_etf
from app.services.price_sync import sync_asset_prices

logger = logging.getLogger(__name__)


async def list_pseudo_etfs(db: AsyncSession):
    return await PseudoEtfRepository(db).list_all()


async def create_pseudo_etf(db: AsyncSession, **kwargs):
    repo = PseudoEtfRepository(db)
    if await repo.get_by_name(kwargs["name"]):
        raise HTTPException(400, "Pseudo-ETF with this name already exists")
    return await repo.create(**kwargs)


async def get_pseudo_etf_detail(db: AsyncSession, etf_id: int):
    return await get_pseudo_etf(etf_id, db)


UPDATABLE_FIELDS = {"name", "description", "base_date"}


async def update_pseudo_etf(db: AsyncSession, etf_id: int, data: dict):
    etf = await get_pseudo_etf(etf_id, db)
    for field, value in data.items():
        if field not in UPDATABLE_FIELDS:
            raise HTTPException(400, f"Field '{field}' is not updatable")
        setattr(etf, field, value)
    return await PseudoEtfRepository(db).save(etf)


async def delete_pseudo_etf(db: AsyncSession, etf_id: int):
    etf = await get_pseudo_etf(etf_id, db)
    await PseudoEtfRepository(db).delete(etf)


async def add_constituents(db: AsyncSession, etf_id: int, asset_ids: list[int]):
    etf = await get_pseudo_etf(etf_id, db)
    assets = await AssetRepository(db).get_by_ids(asset_ids)
    existing_ids = {a.id for a in etf.constituents}
    new_assets = [a for a in assets if a.id not in existing_ids]
    for asset in new_assets:
        etf.constituents.append(asset)
    result = await PseudoEtfRepository(db).save(etf)

    # Sync price history for any new constituent that lacks data
    if new_assets:
        new_ids = [a.id for a in new_assets]
        last_dates = await PriceRepository(db).get_last_dates(new_ids)
        for asset in new_assets:
            if asset.id not in last_dates:
                logger.info("Syncing prices for new constituent %s", asset.symbol)
                await sync_asset_prices(db, asset, period="5y")

    return result


async def remove_constituent(db: AsyncSession, etf_id: int, asset_id: int):
    etf = await get_pseudo_etf(etf_id, db)
    asset = next((a for a in etf.constituents if a.id == asset_id), None)
    if not asset:
        raise HTTPException(404, "Asset not in this pseudo-ETF")
    etf.constituents.remove(asset)
    return await PseudoEtfRepository(db).save(etf)


# --- Thesis ---

async def get_thesis(db: AsyncSession, etf_id: int):
    etf = await get_pseudo_etf(etf_id, db)
    thesis = await PseudoEtfRepository(db).get_thesis(etf_id)
    if not thesis:
        return ThesisResponse(content="", updated_at=etf.created_at)
    return thesis


async def upsert_thesis(db: AsyncSession, etf_id: int, content: str):
    await get_pseudo_etf(etf_id, db)
    return await PseudoEtfRepository(db).upsert_thesis(etf_id, content)


# --- Annotations ---

async def list_annotations(db: AsyncSession, etf_id: int):
    await get_pseudo_etf(etf_id, db)
    return await PseudoEtfRepository(db).list_annotations(etf_id)


async def create_annotation(db: AsyncSession, etf_id: int, **kwargs):
    await get_pseudo_etf(etf_id, db)
    return await PseudoEtfRepository(db).create_annotation(pseudo_etf_id=etf_id, **kwargs)


async def delete_annotation(db: AsyncSession, etf_id: int, annotation_id: int):
    await get_pseudo_etf(etf_id, db)
    repo = PseudoEtfRepository(db)
    annotation = await repo.get_annotation(annotation_id, etf_id)
    if not annotation:
        raise HTTPException(404, "Annotation not found")
    await repo.delete_annotation(annotation)

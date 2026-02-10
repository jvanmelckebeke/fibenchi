from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pseudo_etf import PseudoETF, pseudo_etf_constituents
from app.models.asset import Asset
from app.schemas.pseudo_etf import (
    PseudoETFCreate,
    PseudoETFUpdate,
    PseudoETFAddConstituents,
    PseudoETFResponse,
    PerformancePoint,
)
from app.services.pseudo_etf import calculate_performance

router = APIRouter(prefix="/api/pseudo-etfs", tags=["pseudo-etfs"])


@router.get("", response_model=list[PseudoETFResponse])
async def list_pseudo_etfs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PseudoETF).order_by(PseudoETF.name))
    return result.scalars().all()


@router.post("", response_model=PseudoETFResponse, status_code=201)
async def create_pseudo_etf(data: PseudoETFCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(PseudoETF).where(PseudoETF.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Pseudo-ETF with this name already exists")

    etf = PseudoETF(
        name=data.name,
        description=data.description,
        base_date=data.base_date,
        base_value=data.base_value,
    )
    db.add(etf)
    await db.commit()
    await db.refresh(etf)
    return etf


@router.get("/{etf_id}", response_model=PseudoETFResponse)
async def get_pseudo_etf(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")
    return etf


@router.put("/{etf_id}", response_model=PseudoETFResponse)
async def update_pseudo_etf(etf_id: int, data: PseudoETFUpdate, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(etf, field, value)

    await db.commit()
    await db.refresh(etf)
    return etf


@router.delete("/{etf_id}", status_code=204)
async def delete_pseudo_etf(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")
    await db.delete(etf)
    await db.commit()


@router.post("/{etf_id}/constituents", response_model=PseudoETFResponse)
async def add_constituents(
    etf_id: int, data: PseudoETFAddConstituents, db: AsyncSession = Depends(get_db)
):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    result = await db.execute(select(Asset).where(Asset.id.in_(data.asset_ids)))
    assets = result.scalars().all()

    existing_ids = {a.id for a in etf.constituents}
    for asset in assets:
        if asset.id not in existing_ids:
            etf.constituents.append(asset)

    await db.commit()
    await db.refresh(etf)
    return etf


@router.delete("/{etf_id}/constituents/{asset_id}", response_model=PseudoETFResponse)
async def remove_constituent(
    etf_id: int, asset_id: int, db: AsyncSession = Depends(get_db)
):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    asset = next((a for a in etf.constituents if a.id == asset_id), None)
    if not asset:
        raise HTTPException(404, "Asset not in this pseudo-ETF")

    etf.constituents.remove(asset)
    await db.commit()
    await db.refresh(etf)
    return etf


@router.get("/{etf_id}/performance", response_model=list[PerformancePoint])
async def get_performance(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    asset_ids = [a.id for a in etf.constituents]
    if not asset_ids:
        return []

    return await calculate_performance(db, asset_ids, etf.base_date, float(etf.base_value))

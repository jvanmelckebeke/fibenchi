from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Asset, Thesis
from app.schemas.thesis import ThesisResponse, ThesisUpdate

router = APIRouter(prefix="/api/assets/{symbol}/thesis", tags=["thesis"])


@router.get("", response_model=ThesisResponse)
async def get_thesis(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")

    result = await db.execute(select(Thesis).where(Thesis.asset_id == asset.id))
    thesis = result.scalar_one_or_none()
    if not thesis:
        return ThesisResponse(content="", updated_at=asset.created_at)

    return thesis


@router.put("", response_model=ThesisResponse)
async def update_thesis(symbol: str, data: ThesisUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")

    result = await db.execute(select(Thesis).where(Thesis.asset_id == asset.id))
    thesis = result.scalar_one_or_none()

    if thesis:
        thesis.content = data.content
    else:
        thesis = Thesis(asset_id=asset.id, content=data.content)
        db.add(thesis)

    await db.commit()
    await db.refresh(thesis)
    return thesis

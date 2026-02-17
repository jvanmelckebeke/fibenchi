from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.entity_lookups import get_asset
from app.schemas.thesis import ThesisResponse, ThesisUpdate
from app.services import thesis_service

router = APIRouter(prefix="/api/assets/{symbol}/thesis", tags=["thesis"])


@router.get("", response_model=ThesisResponse, summary="Get investment thesis for an asset")
async def get_thesis(symbol: str, db: AsyncSession = Depends(get_db)):
    asset = await get_asset(symbol, db)
    return await thesis_service.get_thesis(db, asset.id, asset.created_at)


@router.put("", response_model=ThesisResponse, summary="Create or update investment thesis")
async def update_thesis(symbol: str, data: ThesisUpdate, db: AsyncSession = Depends(get_db)):
    asset = await get_asset(symbol, db)
    return await thesis_service.upsert_thesis(db, asset.id, data.content)

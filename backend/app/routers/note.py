from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.note import NoteResponse, NoteUpdate
from app.services import note_service
from app.services.entity_lookups import get_asset

router = APIRouter(prefix="/api/assets/{symbol}/note", tags=["note"])


@router.get("", response_model=NoteResponse, summary="Get note for an asset")
async def get_note(symbol: str, db: AsyncSession = Depends(get_db)):
    asset = await get_asset(symbol, db)
    return await note_service.get_note(db, asset.id, asset.created_at)


@router.put("", response_model=NoteResponse, summary="Create or update note")
async def update_note(symbol: str, data: NoteUpdate, db: AsyncSession = Depends(get_db)):
    asset = await get_asset(symbol, db)
    return await note_service.upsert_note(db, asset.id, data.content)

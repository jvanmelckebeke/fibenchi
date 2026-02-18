from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.settings import SettingsResponse, SettingsUpdate
from app.services import settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse, summary="Get user settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Return the current user settings as a JSON object.

    Returns `{\"data\": {}}` if no settings have been saved yet.
    """
    return await settings_service.get_settings(db)


@router.put("", response_model=SettingsResponse, summary="Update user settings")
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    """Replace the user settings object. The `data` field is a free-form JSON
    object storing preferences like `group_show_rsi`, `compact_mode`, etc.
    """
    return await settings_service.update_settings(db, body.data)

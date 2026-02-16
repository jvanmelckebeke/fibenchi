from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user_settings import UserSettings
from app.schemas.settings import SettingsResponse, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse, summary="Get user settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Return the current user settings as a JSON object.

    Returns `{\"data\": {}}` if no settings have been saved yet.
    """
    result = await db.execute(select(UserSettings).where(UserSettings.id == 1))
    row = result.scalar_one_or_none()
    if not row:
        return SettingsResponse(data={})
    return row


@router.put("", response_model=SettingsResponse, summary="Update user settings")
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    """Replace the user settings object. The `data` field is a free-form JSON
    object storing preferences like `watchlist_show_rsi`, `compact_mode`, etc.
    """
    result = await db.execute(select(UserSettings).where(UserSettings.id == 1))
    row = result.scalar_one_or_none()
    if row:
        row.data = body.data
    else:
        row = UserSettings(id=1, data=body.data)
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return row

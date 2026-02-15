from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user_settings import UserSettings
from app.schemas.settings import SettingsResponse, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse, summary="Get user settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserSettings).where(UserSettings.id == 1))
    row = result.scalar_one_or_none()
    if not row:
        return SettingsResponse(data={})
    return row


@router.put("", response_model=SettingsResponse, summary="Update user settings")
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
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

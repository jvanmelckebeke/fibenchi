from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.companion import MoveScales
from app.services.move_scale_service import book_move_scales

router = APIRouter(prefix="/api/move-scales", tags=["sparklines"])


@router.get(
    "",
    response_model=dict[str, MoveScales],
    summary="Each tracked symbol's own distribution of window moves",
)
async def get_move_scales(db: AsyncSession = Depends(get_db)):
    """symbol -> move scale per board window, for every symbol in a group or thesis.

    The same scales the companion pulse carries. The board places the live
    window move on them to size its move bars.
    """
    return await book_move_scales(db)

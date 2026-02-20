from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.search import SymbolSearchResponse
from app.services import search_service

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[SymbolSearchResponse])
async def search_symbols(
    q: str = Query(..., min_length=1, max_length=50),
    source: Literal["all", "local", "yahoo"] = Query("all"),
    db: AsyncSession = Depends(get_db),
):
    """Search for ticker symbols by name or symbol prefix.

    source controls which backend to query:
      - all (default): local DB first, Yahoo fallback if < 8 local results
      - local: only the pre-seeded symbol_directory (instant)
      - yahoo: only Yahoo Finance, excluding symbols already in local results
    """
    if source == "local":
        return await search_service.search_local(q, db)
    if source == "yahoo":
        return await search_service.search_yahoo(q, db)
    return await search_service.search_symbols(q, db)

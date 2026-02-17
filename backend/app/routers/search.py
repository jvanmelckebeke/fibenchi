from fastapi import APIRouter, Query

from app.services import search_service

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search_symbols(q: str = Query(..., min_length=1, max_length=50)):
    """Search for ticker symbols by name or symbol prefix."""
    return await search_service.search_symbols(q)

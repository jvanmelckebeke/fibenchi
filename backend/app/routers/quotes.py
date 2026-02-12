from fastapi import APIRouter, Query

from app.schemas.quote import QuoteResponse
from app.services.yahoo import batch_fetch_quotes

router = APIRouter(prefix="/api", tags=["quotes"])


@router.get("/quotes", response_model=list[QuoteResponse], summary="Get real-time quotes for symbols")
async def get_quotes(symbols: str = Query(..., description="Comma-separated list of symbols")):
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return []
    return batch_fetch_quotes(symbol_list)

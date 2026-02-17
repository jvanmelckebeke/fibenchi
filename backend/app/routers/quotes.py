from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.schemas.quote import QuoteResponse
from app.services import quote_service

router = APIRouter(prefix="/api", tags=["quotes"])


@router.get("/quotes", response_model=list[QuoteResponse], summary="Get real-time quotes for symbols")
async def get_quotes(symbols: str = Query(..., description="Comma-separated list of symbols")):
    """Fetch latest market quotes for one or more symbols via Yahoo Finance.

    Pass a comma-separated list of ticker symbols (e.g. `AAPL,MSFT,GOOGL`).
    Returns price, previous close, change, change percent, currency, and market state.
    """
    return await quote_service.get_quotes(symbols)


@router.get(
    "/quotes/stream",
    summary="SSE stream of watchlisted quotes (delta compressed)",
    responses={200: {"content": {"text/event-stream": {}}, "description": "Server-Sent Events stream. Each event has `event: quotes` with JSON data containing only the symbols whose quote changed since the last push. The first event contains all watchlisted symbols."}},
)
async def stream_quotes():
    """Open a Server-Sent Events stream that pushes real-time quotes for all
    watchlisted assets.

    **Delta compression:** After the initial full payload, only symbols whose
    data has changed since the previous push are included — reducing bandwidth
    when prices are stable or markets are closed.

    **Adaptive intervals:** The server adjusts the push frequency based on
    market state:
    - **15 s** during regular trading hours (`REGULAR`)
    - **60 s** during pre/post-market sessions
    - **300 s** when all markets are closed

    Each SSE event uses `event: quotes` with a JSON object keyed by symbol.
    """
    return StreamingResponse(
        quote_service.quote_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

import asyncio
import json
import logging

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.database import async_session
from app.models.asset import Asset
from app.schemas.quote import QuoteResponse
from app.services.yahoo import batch_fetch_quotes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["quotes"])


@router.get("/quotes", response_model=list[QuoteResponse], summary="Get real-time quotes for symbols")
async def get_quotes(symbols: str = Query(..., description="Comma-separated list of symbols")):
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return []
    return batch_fetch_quotes(symbol_list)


async def _quote_event_generator():
    """Yield SSE events with watchlisted quotes, adapting interval to market state.

    After the initial full payload, only symbols whose data changed since the
    last push are included (delta mode).  This dramatically reduces bandwidth
    when most markets are closed or prices are stable.
    """
    last_payload: dict[str, dict] = {}

    while True:
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(Asset.symbol).where(Asset.watchlisted.is_(True))
                )
                symbols = [row[0] for row in result.all()]

            if not symbols:
                yield "event: quotes\ndata: {}\n\n"
                last_payload = {}
                await asyncio.sleep(60)
                continue

            quotes = await asyncio.to_thread(batch_fetch_quotes, symbols)

            # Build keyed payload
            full_payload: dict[str, dict] = {}
            market_states: set[str] = set()
            for q in quotes:
                full_payload[q["symbol"]] = q
                if q.get("market_state"):
                    market_states.add(q["market_state"])

            # Compute delta: only symbols that changed since last push
            if last_payload:
                delta = {
                    sym: data
                    for sym, data in full_payload.items()
                    if last_payload.get(sym) != data
                }
            else:
                # First event — send everything
                delta = full_payload

            if delta:
                yield f"event: quotes\ndata: {json.dumps(delta)}\n\n"

            last_payload = full_payload

            # Adapt interval based on market state
            if "REGULAR" in market_states:
                interval = 15
            elif market_states & {"PRE", "POST", "PREPRE", "POSTPOST"}:
                interval = 60
            else:
                interval = 300

            await asyncio.sleep(interval)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Quote stream error")
            await asyncio.sleep(30)


@router.get("/quotes/stream", summary="SSE stream of watchlisted quotes")
async def stream_quotes():
    return StreamingResponse(
        _quote_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

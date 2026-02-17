"""Quote business logic — REST + SSE stream generation."""

import asyncio
import json
import logging

from app.database import async_session
from app.repositories.asset_repo import AssetRepository
from app.services.yahoo import batch_fetch_quotes

logger = logging.getLogger(__name__)


async def get_quotes(symbols: str) -> list[dict]:
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return []
    return await batch_fetch_quotes(symbol_list)


async def quote_event_generator():
    """Yield SSE events with watchlisted quotes, adapting interval to market state.

    After the initial full payload, only symbols whose data changed since the
    last push are included (delta mode).  This dramatically reduces bandwidth
    when most markets are closed or prices are stable.
    """
    last_payload: dict[str, dict] = {}

    while True:
        try:
            async with async_session() as db:
                symbols = await AssetRepository(db).list_watchlisted_symbols()

            if not symbols:
                yield "event: quotes\ndata: {}\n\n"
                last_payload = {}
                await asyncio.sleep(60)
                continue

            quotes = await batch_fetch_quotes(symbols)

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

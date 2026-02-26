"""Quote business logic — REST + SSE stream generation."""

import asyncio
import json
import logging
import time as _time

from app.database import async_session
from app.repositories.asset_repo import AssetRepository
from app.services.intraday import get_intraday_bars
from app.services.price_providers import get_price_provider

logger = logging.getLogger(__name__)

# Cache asset list to avoid opening a DB session every SSE iteration
_asset_list_cache: tuple[float, list[tuple[int, str]]] = (0.0, [])
_ASSET_LIST_TTL = 30  # seconds


def _reset_asset_list_cache() -> None:
    """Reset the asset list cache (useful for testing)."""
    global _asset_list_cache
    _asset_list_cache = (0.0, [])


async def get_quotes(symbols: str) -> list[dict]:
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return []
    return await get_price_provider().batch_fetch_quotes(symbol_list)


async def quote_event_generator():
    """Yield SSE events with quotes for all grouped assets, adapting interval to market state.

    After the initial full payload, only symbols whose data changed since the
    last push are included (delta mode).  This dramatically reduces bandwidth
    when most markets are closed or prices are stable.

    Also pushes ``event: intraday`` with 1-minute bars for the live day view.
    First push sends full day data, subsequent pushes send only new bars (delta).
    """
    last_payload: dict[str, dict] = {}
    # Track last pushed intraday bar timestamp per symbol
    last_intraday_ts: dict[str, int] = {}

    while True:
        try:
            global _asset_list_cache
            now = _time.monotonic()
            if now - _asset_list_cache[0] > _ASSET_LIST_TTL:
                async with async_session() as db:
                    pairs = await AssetRepository(db).list_in_any_group_id_symbol_pairs()
                _asset_list_cache = (now, pairs)
            else:
                pairs = _asset_list_cache[1]

            symbols = [sym for _, sym in pairs]
            asset_map_id_to_sym = {aid: sym for aid, sym in pairs}
            asset_ids = [aid for aid, _ in pairs]

            if not symbols:
                yield "event: quotes\ndata: {}\n\n"
                last_payload = {}
                last_intraday_ts = {}
                await asyncio.sleep(60)
                continue

            quotes = await get_price_provider().batch_fetch_quotes(symbols)

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

            # Push intraday bars (full on first push, delta after)
            active_states = {"REGULAR", "PRE", "POST", "PREPRE", "POSTPOST"}
            has_active_market = bool(market_states & active_states)

            # Always push intraday on first iteration or when markets are active
            if has_active_market or not last_intraday_ts:
                async with async_session() as db:
                    all_bars = await get_intraday_bars(db, asset_ids, asset_map_id_to_sym)

                if all_bars:
                    if not last_intraday_ts:
                        # First push: send full data
                        intraday_payload = all_bars
                    else:
                        # Delta: only new bars since last push
                        intraday_payload = {}
                        for sym, bars in all_bars.items():
                            last_ts = last_intraday_ts.get(sym, 0)
                            new_bars = [b for b in bars if b["time"] > last_ts]
                            if new_bars:
                                intraday_payload[sym] = new_bars

                    if intraday_payload:
                        yield f"event: intraday\ndata: {json.dumps(intraday_payload)}\n\n"

                    # Update last pushed timestamps
                    for sym, bars in all_bars.items():
                        if bars:
                            last_intraday_ts[sym] = max(b["time"] for b in bars)

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

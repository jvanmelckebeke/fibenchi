"""Quote business logic — REST + SSE stream generation."""

import asyncio
import logging
import time as _time
from collections.abc import Sequence

from pydantic import TypeAdapter

from app.database import async_session
from app.domain import AssetRef
from app.domain.market_state import any_active, state_info
from app.domain.phases import Phase
from app.repositories.asset_repo import AssetRepository
from app.schemas.intraday import IntradayBar
from app.schemas.quote import Quote
from app.services.intraday import get_intraday_bars
from app.services.market_calendar import schedule_poll_hint
from app.services.price_providers import get_price_provider

logger = logging.getLogger(__name__)

# Serializers for the SSE event payloads (both keyed by symbol).
_quotes_payload_adapter = TypeAdapter(dict[str, Quote])
_intraday_payload_adapter = TypeAdapter(dict[str, list[IntradayBar]])

# Cache asset list to avoid opening a DB session every SSE iteration
_asset_list_cache: tuple[float, list[AssetRef]] = (0.0, [])
_ASSET_LIST_TTL = 30  # seconds


def _reset_asset_list_cache() -> None:
    """Reset the asset list cache (useful for testing)."""
    global _asset_list_cache
    _asset_list_cache = (0.0, [])


def _poll_interval(market_states: set[str], symbols: Sequence[str], at=None) -> int:
    """Seconds until the next quote poll.

    The live market states pick the cadence whenever they exist — they know
    about halts, special sessions, and closures a stale calendar wouldn't, so
    an explicit CLOSED must never be overridden by the schedule. The venue
    schedule steps in two ways:

    - when the quote batch is degraded (no states at all), the scheduled
      phase substitutes for the missing live answer, so a dead feed during
      regular hours doesn't drop the stream to the 300s closed cadence;
    - an all-closed stream sleeps until the next opening bell instead of up
      to 5 minutes past it (one cheap poll at the bell discovers the flip).
    """
    if any(state_info(s).phase == Phase.OPEN for s in market_states):
        live = 15
    elif any_active(market_states):
        live = 60
    else:
        live = 300

    phase, next_open_secs = schedule_poll_hint(symbols, at)

    if market_states:
        interval = live
    else:
        scheduled = 15 if phase == Phase.OPEN else 60 if phase in (Phase.PREMARKET, Phase.AFTERMARKET) else 300
        interval = min(live, scheduled)
    if next_open_secs is not None:
        # Wake just after the earliest bell (floor 15s so a bell moments away
        # can't busy-loop the stream).
        interval = min(interval, max(15, int(next_open_secs) + 1))
    return interval


async def get_quotes(symbols: str) -> list[Quote]:
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return []
    return await get_price_provider().batch_fetch_quotes(symbol_list)


async def quote_event_generator(intraday_symbols: frozenset[str] | None = None):
    """Yield SSE events with quotes for all grouped assets, adapting interval to market state.

    After the initial full payload, only symbols whose data changed since the
    last push are included (delta mode).  This dramatically reduces bandwidth
    when most markets are closed or prices are stable.

    ``intraday_symbols`` opts the connection in to ``event: intraday``, the
    1-minute bars behind the live day view. First push sends the full window,
    later pushes only new bars (delta).

    **Intraday is opt-in and scoped.** Quotes are small and every page shows
    them, so they go to everyone; a full bar set is not — measured at 738 KiB
    for 78 symbols (#615), re-sent on every reconnect. Only two views draw
    bars, and each wants a handful of symbols, so a connection that doesn't ask
    gets none. Passing ``None`` is therefore *silence*, not *everything*: the
    saving is automatic and a caller cannot forget to ask for less.
    """
    last_payload: dict[str, Quote] = {}
    # Track last pushed intraday bar timestamp per symbol
    last_intraday_ts: dict[str, int] = {}
    wanted_intraday = frozenset(intraday_symbols or ())

    while True:
        try:
            global _asset_list_cache
            now = _time.monotonic()
            if now - _asset_list_cache[0] > _ASSET_LIST_TTL:
                async with async_session() as db:
                    refs = await AssetRepository(db).list_in_any_group_refs()
                _asset_list_cache = (now, refs)
            else:
                refs = _asset_list_cache[1]

            if not refs:
                yield "event: quotes\ndata: {}\n\n"
                last_payload = {}
                last_intraday_ts = {}
                await asyncio.sleep(60)
                continue

            quotes = await get_price_provider().batch_fetch_quotes(list(refs))

            # Build keyed payload
            full_payload: dict[str, Quote] = {}
            market_states: set[str] = set()
            for q in quotes:
                full_payload[q.symbol] = q
                if q.market_state:
                    market_states.add(q.market_state)

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
                data = _quotes_payload_adapter.dump_json(delta).decode()
                yield f"event: quotes\ndata: {data}\n\n"

            last_payload = full_payload

            # Push intraday bars (full on first push, delta after)
            has_active_market = any_active(market_states)

            # Always push intraday on first iteration or when markets are active
            if wanted_intraday and (has_active_market or not last_intraday_ts):
                # Scoped to what this connection asked for. Filtering the refs
                # rather than the result keeps the DB from reading bars nobody
                # will draw — the query is the expensive half, not the JSON.
                bar_refs = [r for r in refs if r.symbol in wanted_intraday]
                async with async_session() as db:
                    all_bars = await get_intraday_bars(db, bar_refs)

                if all_bars:
                    if not last_intraday_ts:
                        # First push: send full data
                        intraday_payload = all_bars
                    else:
                        # Delta: only new bars since last push
                        intraday_payload = {}
                        for sym, bars in all_bars.items():
                            last_ts = last_intraday_ts.get(sym, 0)
                            new_bars = [b for b in bars if b.time > last_ts]
                            if new_bars:
                                intraday_payload[sym] = new_bars

                    if intraday_payload:
                        data = _intraday_payload_adapter.dump_json(intraday_payload).decode()
                        yield f"event: intraday\ndata: {data}\n\n"

                    # Update last pushed timestamps
                    for sym, bars in all_bars.items():
                        if bars:
                            last_intraday_ts[sym] = max(b.time for b in bars)

            await asyncio.sleep(_poll_interval(market_states, refs))

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Quote stream error")
            await asyncio.sleep(30)

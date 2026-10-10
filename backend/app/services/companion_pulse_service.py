"""Assemble the companion pulse bundle: recent closes and σ-Move state per tracked symbol.

The values come from the same indicator frame the web's snapshots are built
from (``compute_ref_indicators`` over the same history window), so the app's
σ-Move for a stored bar matches the board's.

Stored bars are already in the major currency unit: the Yahoo client divides
subunit quotes (GBp, ILA, ZAc) by their divisor before anything is written, so
closes pass through as stored.
"""

import asyncio
import datetime
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AssetRef
from app.models import PriceHistory
from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.schemas.companion import (
    PULSE_VERSION,
    CompanionPulse,
    MoveScales,
    PulseClose,
    PulsePoint,
    PulseSymbol,
)
from app.services.compute.group import compute_ref_indicators, load_indicator_history
from app.services.compute.indicators import INDICATOR_REGISTRY, safe_round, vnr_usable_returns
from app.services.move_scale_service import book_move_scales
from app.utils import TTLCache

#: Calendar days of closes before each symbol's latest bar.
CLOSES_WINDOW_DAYS = 40
#: Stored bars carried with their σ-Move readings.
TAIL_BARS = 2

_VNR = INDICATOR_REGISTRY["vnr"]

# Keyed like the batch indicator cache: (frozenset of symbols, latest stored
# bar date). Every price write calls invalidate_pulse_cache, and the refresh
# jobs re-warm it afterwards, so the TTL only has to outlast the gap between
# refreshes for the first app open of the morning to find it warm.
_pulse_cache: TTLCache = TTLCache(default_ttl=24 * 3600, max_size=4)


def invalidate_pulse_cache(symbols: Iterable[str]) -> int:
    """Drop cached bundles covering any of ``symbols``. Returns entries removed."""
    wanted = {str(s) for s in symbols}
    if not wanted:
        return 0
    return _pulse_cache.invalidate(lambda key: bool(key[0] & wanted))


def _round(value, column: str) -> float | None:
    return safe_round(value, _VNR.field_decimals.get(column, _VNR.decimals))


def _pulse_symbol(ref: AssetRef, prices: list[PriceHistory], move_scale: MoveScales | None) -> PulseSymbol:
    indicators = compute_ref_indicators(ref, prices)
    # vnr_gap_sessions and vnr_ex_div equal the gap series and the dividends
    # everywhere the count can see them (gaps > 1, payouts > 0), so this is
    # the same series the warmup gate counted.
    returns = vnr_usable_returns(
        indicators["close"], indicators["vnr_gap_sessions"], indicators["vnr_ex_div"]
    ).notna().cumsum()

    latest = indicators.index[-1]
    window_start = latest - datetime.timedelta(days=CLOSES_WINDOW_DAYS)
    closes = [
        PulseClose(date=d, close=round(float(c), 4))
        for d, c in indicators.loc[indicators.index >= window_start, "close"].items()
    ]

    tail = []
    for d, row in indicators.tail(TAIL_BARS).iterrows():
        gap = safe_round(row["vnr_gap_sessions"], 0)
        tail.append(
            PulsePoint(
                date=d,
                close=round(float(row["close"]), 4),
                vnr=_round(row["vnr"], "vnr"),
                vnr_sigma=_round(row["vnr_sigma"], "vnr_sigma"),
                gap_sessions=int(gap) if gap is not None else None,
                returns=int(returns.loc[d]),
            )
        )
    return PulseSymbol(closes=closes, tail=tail, move_scale=move_scale)


def _assemble(
    refs: list[AssetRef],
    history: dict[AssetRef, list[PriceHistory]],
    scales: dict[str, MoveScales],
) -> CompanionPulse:
    symbols: dict[str, PulseSymbol] = {}
    missing: list[str] = []
    for ref in sorted(refs, key=str):
        prices = history.get(ref)
        if not prices:
            missing.append(ref.symbol)
            continue
        symbols[ref.symbol] = _pulse_symbol(ref, prices, scales.get(ref.symbol))
    return CompanionPulse(
        version=PULSE_VERSION,
        generated_at=datetime.datetime.now(datetime.UTC),
        symbols=symbols,
        missing=missing,
    )


async def build_pulse(db: AsyncSession) -> CompanionPulse:
    """The pulse for every tracked symbol, from cache when the book and its bars are unchanged."""
    refs = [ref for ref in await AssetRepository(db).list_in_any_group_or_thesis_refs() if ref.id is not None]
    latest_date = await PriceRepository(db).get_latest_date([ref.id for ref in refs])
    cache_key = (frozenset(ref.symbol for ref in refs), latest_date)

    cached = _pulse_cache.get_value(cache_key)
    if cached is not None:
        return cached

    history = await load_indicator_history(db, refs)
    scales = await book_move_scales(db)
    # The indicator pass over the whole book is seconds of pandas work, so it
    # runs off the event loop to keep the SSE stream and other requests moving.
    pulse = await asyncio.to_thread(_assemble, refs, history, scales)
    _pulse_cache.set_value(cache_key, pulse)
    return pulse

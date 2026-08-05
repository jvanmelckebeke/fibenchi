"""Batch data query service — fetches quotes, snapshots, prices, and indicators for arbitrary symbols."""

import logging

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset
from app.schemas.batch_data import SymbolBatchData
from app.schemas.price import DatedOHLCV
from app.services import price_service
from app.services.compute.indicators import compute_batch_indicator_snapshots
from app.services.entity_lookups import find_asset
from app.services.price_providers import get_price_provider

logger = logging.getLogger(__name__)

ALLOWED_FIELDS = frozenset({"quote", "snapshot", "prices", "indicators"})
MAX_SYMBOLS = 50


async def query_batch_data(
    db: AsyncSession,
    symbols: list[str],
    fields: set[str],
    period: str,
) -> dict[str, SymbolBatchData]:
    """Fetch requested data fields for multiple symbols.

    Returns :class:`SymbolBatchData` per symbol — the requested fields, or
    ``error`` if the symbol failed entirely.

    Tracked assets (in DB) use cached prices; untracked symbols are fetched
    ephemerally from the configured price provider.
    """
    results: dict[str, dict] = {sym: {} for sym in symbols}
    symbol_errors: dict[str, str] = {}

    # --- Batch: quotes (single provider call for all symbols) ---
    if "quote" in fields:
        try:
            quotes = await get_price_provider().batch_fetch_quotes(symbols)
            for q in quotes:
                sym = q.get("symbol")
                if sym and sym in results:
                    results[sym]["quote"] = q
        except Exception:
            logger.exception("Batch quote fetch failed")

    # --- Batch: snapshots (single provider call for all symbols) ---
    if "snapshot" in fields:
        try:
            snapshots = await compute_batch_indicator_snapshots(symbols)
            for snap in snapshots:
                sym = snap.get("symbol")
                if sym and sym in results:
                    snap_data = {k: v for k, v in snap.items() if k != "symbol"}
                    # Only include if we got actual computed data
                    if snap_data.get("close") is not None:
                        results[sym]["snapshot"] = snap_data
        except Exception:
            logger.exception("Batch snapshot fetch failed")

    # --- Per-symbol: prices and/or indicators ---
    if fields & {"prices", "indicators"}:
        asset_map: dict[str, Asset | None] = {}
        for sym in symbols:
            asset_map[sym] = await find_asset(sym, db)

        for sym in symbols:
            asset = asset_map.get(sym)

            if "prices" in fields and sym not in symbol_errors:
                try:
                    raw = await price_service.get_prices(db, asset, sym, period)
                    results[sym]["prices"] = [DatedOHLCV.model_validate(p) for p in raw]
                except HTTPException:
                    symbol_errors[sym] = f"No price data available for {sym}"
                except Exception:
                    logger.exception(f"Price fetch failed for {sym}")
                    symbol_errors[sym] = f"Price fetch failed for {sym}"

            if "indicators" in fields and sym not in symbol_errors:
                try:
                    raw = await price_service.get_indicators(db, asset, sym, period)
                    results[sym]["indicators"] = list(raw)  # already IndicatorResponse models
                except HTTPException:
                    symbol_errors.setdefault(sym, f"No indicator data available for {sym}")
                except Exception:
                    logger.exception(f"Indicator fetch failed for {sym}")
                    symbol_errors.setdefault(sym, f"Indicator fetch failed for {sym}")

    # Build final response
    final: dict[str, SymbolBatchData] = {}
    for sym in symbols:
        if results[sym]:
            final[sym] = SymbolBatchData(**results[sym])
        elif sym in symbol_errors:
            final[sym] = SymbolBatchData(error=symbol_errors[sym])
        else:
            final[sym] = SymbolBatchData(error=f"No data available for {sym}")

    return final

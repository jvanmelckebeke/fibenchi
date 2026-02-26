"""Batch data query service — fetches quotes, snapshots, prices, and indicators for arbitrary symbols."""

import logging
from datetime import date

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset
from app.services import price_service
from app.services.compute.indicators import compute_batch_indicator_snapshots
from app.services.entity_lookups import find_asset
from app.services.price_providers import get_price_provider

logger = logging.getLogger(__name__)

ALLOWED_FIELDS = frozenset({"quote", "snapshot", "prices", "indicators"})
MAX_SYMBOLS = 50


def _serialize_price(p) -> dict:
    """Convert a PriceHistory ORM object or PriceResponse Pydantic model to a plain dict."""
    if hasattr(p, "model_dump"):
        d = p.model_dump()
        if isinstance(d.get("date"), date):
            d["date"] = d["date"].isoformat()
        return d
    return {
        "date": p.date.isoformat() if isinstance(p.date, date) else str(p.date),
        "open": round(float(p.open), 4),
        "high": round(float(p.high), 4),
        "low": round(float(p.low), 4),
        "close": round(float(p.close), 4),
        "volume": int(p.volume),
    }


def _serialize_indicator(row) -> dict:
    """Convert an IndicatorResponse Pydantic model to a plain dict."""
    d = row.model_dump()
    if isinstance(d.get("date"), date):
        d["date"] = d["date"].isoformat()
    return d


async def query_batch_data(
    db: AsyncSession,
    symbols: list[str],
    fields: set[str],
    period: str,
) -> dict[str, dict]:
    """Fetch requested data fields for multiple symbols.

    Returns a dict keyed by symbol. Each value is a dict with the requested
    field data, or ``{"error": "..."}`` if the symbol failed entirely.

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
                    results[sym]["prices"] = [_serialize_price(p) for p in raw]
                except HTTPException:
                    symbol_errors[sym] = f"No price data available for {sym}"
                except Exception:
                    logger.exception(f"Price fetch failed for {sym}")
                    symbol_errors[sym] = f"Price fetch failed for {sym}"

            if "indicators" in fields and sym not in symbol_errors:
                try:
                    raw = await price_service.get_indicators(db, asset, sym, period)
                    results[sym]["indicators"] = [_serialize_indicator(i) for i in raw]
                except HTTPException:
                    symbol_errors.setdefault(sym, f"No indicator data available for {sym}")
                except Exception:
                    logger.exception(f"Indicator fetch failed for {sym}")
                    symbol_errors.setdefault(sym, f"Indicator fetch failed for {sym}")

    # Build final response
    final: dict[str, dict] = {}
    for sym in symbols:
        if results[sym]:
            final[sym] = results[sym]
        elif sym in symbol_errors:
            final[sym] = {"error": symbol_errors[sym]}
        else:
            final[sym] = {"error": f"No data available for {sym}"}

    return final

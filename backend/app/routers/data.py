"""Batch data query endpoint for external tooling."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import PeriodType
from app.database import get_db
from app.services.data_service import ALLOWED_FIELDS, MAX_SYMBOLS, query_batch_data

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get(
    "",
    summary="Batch data query for multiple symbols",
    response_description="Dict keyed by symbol with requested data fields, or per-symbol error.",
)
async def get_data(
    symbols: str = Query(
        ...,
        min_length=1,
        description="Comma-separated ticker symbols (e.g. RKLB,IONQ,NET). Max 50.",
    ),
    fields: str = Query(
        "quote,snapshot",
        description="Comma-separated data fields: quote, snapshot, prices, indicators.",
    ),
    period: PeriodType = Query(
        "3mo",
        description="Time period for prices/indicators fields.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Fetch quotes, indicator snapshots, prices, and/or technical indicators
    for one or more ticker symbols in a single request.

    Works for any ticker — tracked assets use cached DB data, untracked symbols
    are fetched ephemerally from the price provider (Yahoo Finance).

    **Fields:**

    - `quote` — Real-time price, change, volume, market state
    - `snapshot` — Latest indicator values (RSI, MACD, ATR, ADX…) and derived signals
    - `prices` — OHLCV price history for the given period
    - `indicators` — Full indicator time series for the given period

    **Response shape:**

        {
          "RKLB": {"quote": {...}, "snapshot": {...}},
          "BADTICKER": {"error": "No data available for BADTICKER"}
        }
    """
    # Parse symbols
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=422, detail="At least one symbol is required")
    if len(symbol_list) > MAX_SYMBOLS:
        raise HTTPException(
            status_code=422, detail=f"Maximum {MAX_SYMBOLS} symbols per request"
        )

    # Parse and validate fields
    field_set = {f.strip().lower() for f in fields.split(",") if f.strip()}
    invalid = field_set - ALLOWED_FIELDS
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid fields: {', '.join(sorted(invalid))}. Allowed: {', '.join(sorted(ALLOWED_FIELDS))}",
        )
    if not field_set:
        raise HTTPException(status_code=422, detail="At least one field is required")

    return await query_batch_data(db, symbol_list, field_set, period)
